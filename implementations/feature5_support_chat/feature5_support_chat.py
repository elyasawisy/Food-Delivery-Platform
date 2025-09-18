from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import psycopg2
import psycopg2.extras
from datetime import datetime
import logging


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret!')

# Initialize SocketIO without specific async mode
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'foodfast_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'port': os.getenv('DB_PORT', '5432')
}

#set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None 


def save_message_to_db(sender_id, receiver_id, message):
    """Save message to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_messages (sender_id, receiver_id, message, created_at, delivered)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (sender_id, receiver_id, message, datetime.now(), True))
            
            message_id = cur.fetchone()[0]
            conn.commit()
            conn.close()
            return message_id
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        if conn:
            conn.close()
        return False

def get_chat_history(user1_id, user2_id, limit=50):
    """Get chat history between two users"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT cm.*, u.name as sender_name
                FROM chat_messages cm
                JOIN users u ON cm.sender_id = u.id
                WHERE (cm.sender_id = %s AND cm.receiver_id = %s)
                   OR (cm.sender_id = %s AND cm.receiver_id = %s)
                ORDER BY cm.created_at ASC
                LIMIT %s
            """, (user1_id, user2_id, user2_id, user1_id, limit))
            
            messages = cur.fetchall()
            conn.close()
            
            # Convert to list of dicts
            return [{
                'id': msg['id'],
                'sender_id': msg['sender_id'],
                'sender_name': msg['sender_name'],
                'message': msg['message'],
                'created_at': msg['created_at'].isoformat(),
                'delivered': msg['delivered']
            } for msg in messages]
            
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        if conn:
            conn.close()
        return []

def validate_user(user_id):
    """Validate if user exists"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            result = cur.fetchone()
            conn.close()
            return result is not None
    except Exception as e:
        logger.error(f"Error validating user: {e}")
        if conn:
            conn.close()
        return False

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'status': 'Connected to support chat'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on("join_chat")
def join_chat(data):
    """Join a chat room and load history"""
    try:
        user_id = data.get("user_id")
        support_agent_id = data.get("support_agent_id", 1)  # Default support agent
        
        # Validate input
        if not user_id:
            emit('error', {'message': 'User ID is required'})
            return
            
        # Validate users exist
        if not validate_user(user_id) or not validate_user(support_agent_id):
            emit('error', {'message': 'Invalid user ID'})
            return
            
        # Create room ID (consistent for both users)
        room = f"chat_{min(user_id, support_agent_id)}_{max(user_id, support_agent_id)}"
        
        # Join the room
        join_room(room)
        
        # Load and send chat history
        history = get_chat_history(user_id, support_agent_id)
        
        emit('joined_chat', {
            'room': room,
            'message': 'Successfully joined chat',
            'history': history
        })
        
        # Notify others in room that user joined
        emit('user_joined', {
            'user_id': user_id,
            'message': f'User {user_id} joined the chat'
        }, room=room, include_self=False)
        
    except Exception as e:
        logger.error(f"Error in join_chat: {e}")
        emit('error', {'message': 'Failed to join chat'})

@socketio.on("leave_chat")
def leave_chat(data):
    """Leave a chat room"""
    try:
        room = data.get("room")
        user_id = data.get("user_id")
        
        if room:
            leave_room(room)
            emit('left_chat', {'message': 'Successfully left chat'})
            
            # Notify others in room
            emit('user_left', {
                'user_id': user_id,
                'message': f'User {user_id} left the chat'
            }, room=room, include_self=False)
            
    except Exception as e:
        logger.error(f"Error in leave_chat: {e}")
        emit('error', {'message': 'Failed to leave chat'})

@socketio.on("send_message")
def send_message(data):
    """Send a message in chat"""
    try:
        room = data.get("room")
        message = data.get("message", "").strip()
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")
        
        # Validate input
        if not all([room, message, sender_id, receiver_id]):
            emit('error', {'message': 'Missing required fields'})
            return
            
        if len(message) > 1000:  # Message length limit
            emit('error', {'message': 'Message too long (max 1000 characters)'})
            return
            
        # Validate users
        if not validate_user(sender_id) or not validate_user(receiver_id):
            emit('error', {'message': 'Invalid user ID'})
            return
            
        # Save message to database
        message_id = save_message_to_db(sender_id, receiver_id, message)
        if not message_id:
            emit('error', {'message': 'Failed to save message'})
            return
            
        # Get sender name
        conn = get_db_connection()
        sender_name = "Unknown"
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM users WHERE id = %s", (sender_id,))
                    result = cur.fetchone()
                    if result:
                        sender_name = result[0]
                conn.close()
            except Exception as e:
                logger.error(f"Error getting sender name: {e}")
                if conn:
                    conn.close()
        
        # Broadcast message to room
        message_data = {
            'id': message_id,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'message': message,
            'created_at': datetime.now().isoformat(),
            'delivered': True
        }
        
        emit('receive_message', message_data, room=room)
        
        # Send delivery confirmation to sender
        emit('message_delivered', {
            'message_id': message_id,
            'status': 'delivered'
        })
        
    except Exception as e:
        logger.error(f"Error in send_message: {e}")
        emit('error', {'message': 'Failed to send message'})

@socketio.on("typing")
def typing(data):
    """Handle typing indicator"""
    try:
        room = data.get("room")
        sender_id = data.get("sender_id")
        is_typing = data.get("is_typing", False)
        
        if not room or not sender_id:
            return
            
        # Get sender name
        conn = get_db_connection()
        sender_name = "Someone"
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM users WHERE id = %s", (sender_id,))
                    result = cur.fetchone()
                    if result:
                        sender_name = result[0]
                conn.close()
            except Exception as e:
                logger.error(f"Error getting sender name for typing: {e}")
                if conn:
                    conn.close()
        
        # Broadcast typing status to room (except sender)
        emit('typing_status', {
            'sender_id': sender_id,
            'sender_name': sender_name,
            'is_typing': is_typing
        }, room=room, include_self=False)
        
    except Exception as e:
        logger.error(f"Error in typing: {e}")

@socketio.on("mark_delivered")
def mark_delivered(data):
    """Mark messages as delivered"""
    try:
        message_ids = data.get("message_ids", [])
        
        if not message_ids:
            return
            
        conn = get_db_connection()
        if not conn:
            return
            
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE chat_messages 
                SET delivered = TRUE 
                WHERE id = ANY(%s)
            """, (message_ids,))
            
        conn.commit()
        conn.close()
        
        emit('messages_marked_delivered', {'message_ids': message_ids})
        
    except Exception as e:
        logger.error(f"Error marking messages as delivered: {e}")
        if conn:
            conn.close()

# REST API endpoints
@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "support_chat"})

@app.route("/api/chat/history/<int:user1_id>/<int:user2_id>")
def get_chat_history_api(user1_id, user2_id):
    """REST API to get chat history"""
    try:
        limit = request.args.get('limit', 50, type=int)
        history = get_chat_history(user1_id, user2_id, limit)
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        logger.error(f"Error in chat history API: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get chat history'
        }), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler"""
    logger.error(f"Unhandled exception: {e}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == "__main__":
    # Test database connection on startup
    conn = get_db_connection()
    if conn:
        logger.info("Database connection successful")
        conn.close()
    else:
        logger.error("Failed to connect to database")
    
    
    # Run with gevent WebSocket support
    socketio.run(app, host="0.0.0.0", port=5005, debug=True)
   
