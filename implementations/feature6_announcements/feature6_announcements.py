from flask import Flask, request, jsonify, Response
from flask_cors import CORS  
import redis
import psycopg2
import psycopg2.extras
import json
import os
from datetime import datetime
import logging
import threading
import time
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration - update environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),  # Changed from 'postgres'
    'database': os.getenv('DB_NAME', 'foodfast_db'),
    'user': os.getenv('DB_USER', 'foodfast'),
    'password': os.getenv('DB_PASSWORD', 'foodfast123'),
    'port': int(os.getenv('DB_PORT', 5432))
}

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")  # Changed from redis:6379

# Add environment file handling
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
try:
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()  # Test connection
    logger.info("Redis connection successful")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    r = None

def get_db_connection():
    """Get database connection with retries"""
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting database connection (attempt {attempt + 1}/{max_retries})")
            logger.info(f"Connection params: host={DB_CONFIG['host']}, port={DB_CONFIG['port']}, db={DB_CONFIG['database']}")
            conn = psycopg2.connect(**DB_CONFIG)
            logger.info(f"Successfully connected to database on attempt {attempt + 1}")
            return conn
        except psycopg2.Error as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    logger.error("All database connection attempts failed")
    return None

def init_announcements_table():
    """Initialize announcements table if not exists"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    announcement_type VARCHAR(50) DEFAULT 'general',
                    target_users TEXT,  -- JSON array of user IDs or 'all'
                    priority VARCHAR(20) DEFAULT 'normal',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    created_by INTEGER REFERENCES users(id)
                );
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_announcements (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    announcement_id INTEGER REFERENCES announcements(id),
                    read_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error initializing announcements table: {e}")
        if conn:
            conn.close()
        return False

def save_announcement_to_db(title, message, announcement_type='general', target_users='all', 
                           priority='normal', expires_at=None, created_by=None):
    """Save announcement to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO announcements (title, message, announcement_type, target_users, 
                                         priority, expires_at, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (title, message, announcement_type, json.dumps(target_users), 
                  priority, expires_at, created_by))
            
            announcement_id = cur.fetchone()[0]
            
            # Create user_announcements records for targeted users
            if target_users == 'all':
                cur.execute("""
                    INSERT INTO user_announcements (user_id, announcement_id)
                    SELECT id, %s FROM users
                """, (announcement_id,))
            else:
                if isinstance(target_users, list):
                    for user_id in target_users:
                        cur.execute("""
                            INSERT INTO user_announcements (user_id, announcement_id)
                            VALUES (%s, %s)
                        """, (user_id, announcement_id))
            
        conn.commit()
        conn.close()
        return announcement_id
    except Exception as e:
        logger.error(f"Error saving announcement: {e}")
        if conn:
            conn.close()
        return None

def get_user_announcements(user_id, unread_only=False, limit=50):
    """Get announcements for a specific user"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            where_clause = "WHERE ua.user_id = %s"
            params = [user_id]
            
            if unread_only:
                where_clause += " AND ua.read_at IS NULL"
                
            where_clause += " AND (a.expires_at IS NULL OR a.expires_at > NOW())"
            
            cur.execute(f"""
                SELECT a.*, ua.read_at, ua.created_at as delivered_at,
                       u.name as created_by_name
                FROM announcements a
                JOIN user_announcements ua ON a.id = ua.announcement_id
                LEFT JOIN users u ON a.created_by = u.id
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT %s
            """, params + [limit])
            
            announcements = cur.fetchall()
            conn.close()
            
            return [{
                'id': ann['id'],
                'title': ann['title'],
                'message': ann['message'],
                'type': ann['announcement_type'],
                'priority': ann['priority'],
                'created_at': ann['created_at'].isoformat(),
                'expires_at': ann['expires_at'].isoformat() if ann['expires_at'] else None,
                'delivered_at': ann['delivered_at'].isoformat() if ann['delivered_at'] else None,
                'read_at': ann['read_at'].isoformat() if ann['read_at'] else None,
                'created_by_name': ann['created_by_name'],
                'is_read': ann['read_at'] is not None
            } for ann in announcements]
            
    except Exception as e:
        logger.error(f"Error getting user announcements: {e}")
        if conn:
            conn.close()
        return []

def mark_announcement_read(user_id, announcement_id):
    """Mark announcement as read by user"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE user_announcements 
                SET read_at = NOW()
                WHERE user_id = %s AND announcement_id = %s AND read_at IS NULL
            """, (user_id, announcement_id))
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error marking announcement as read: {e}")
        if conn:
            conn.close()
        return False

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

def publish_announcement(announcement_data):
    """Publish announcement to Redis for real-time delivery"""
    if r:
        try:
            r.publish("announcements", json.dumps(announcement_data))
            return True
        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")
            return False
    return False

@app.route("/announce", methods=["POST"])
def announce():
    """Create and send system-wide announcement"""
    try:
        data = request.get_json()
        
        # Validate required fields
        title = data.get("title", "").strip()
        message = data.get("message", "").strip()
        
        if not title or not message:
            return jsonify({
                "success": False,
                "error": "Title and message are required"
            }), 400
            
        # Optional fields
        announcement_type = data.get("type", "general")
        target_users = data.get("target_users", "all")
        priority = data.get("priority", "normal")
        expires_at = data.get("expires_at")
        created_by = data.get("created_by")
        
        # Validate priority
        if priority not in ['low', 'normal', 'high', 'urgent']:
            priority = 'normal'
            
        # Validate announcement type
        valid_types = ['general', 'maintenance', 'promotion', 'feature', 'outage']
        if announcement_type not in valid_types:
            announcement_type = 'general'
            
        # Validate target users
        if target_users != 'all' and isinstance(target_users, list):
            # Validate user IDs exist
            valid_users = []
            for user_id in target_users:
                if validate_user(user_id):
                    valid_users.append(user_id)
            target_users = valid_users if valid_users else 'all'
            
        # Parse expires_at if provided
        expires_datetime = None
        if expires_at:
            try:
                expires_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": "Invalid expires_at format. Use ISO format."
                }), 400
                
        # Validate created_by if provided
        if created_by and not validate_user(created_by):
            return jsonify({
                "success": False,
                "error": "Invalid created_by user ID"
            }), 400
            
        # Save to database
        announcement_id = save_announcement_to_db(
            title, message, announcement_type, target_users,
            priority, expires_datetime, created_by
        )
        
        if not announcement_id:
            return jsonify({
                "success": False,
                "error": "Failed to save announcement"
            }), 500
            
        # Prepare announcement data for real-time delivery
        announcement_data = {
            "id": announcement_id,
            "title": title,
            "message": message,
            "type": announcement_type,
            "priority": priority,
            "target_users": target_users,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at
        }
        
        # Publish to Redis for real-time delivery
        publish_success = publish_announcement(announcement_data)
        
        return jsonify({
            "success": True,
            "announcement_id": announcement_id,
            "message": "Announcement sent successfully",
            "real_time_delivered": publish_success,
            "stored_in_db": True
        })
        
    except Exception as e:
        logger.error(f"Error in announce endpoint: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to create announcement"
        }), 500

@app.route("/announcements/stream/<int:user_id>")
def stream_announcements(user_id):
    """SSE endpoint for real-time announcements"""
    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'X-Accel-Buffering': 'no'
    }
    
    # Validate user
    if not validate_user(user_id):
        return jsonify({"error": "Invalid user ID"}), 400
    
    def event_stream():
        try:
            # Send initial connection message
            yield "data: {\"status\":\"connected\"}\n\n"
            
            if not r:
                logger.error("Redis not available for streaming")
                yield f"data: {json.dumps({'error': 'Real-time service unavailable'})}\n\n"
                return
                
            # Subscribe to Redis announcements
            pubsub = r.pubsub()
            pubsub.subscribe("announcements")
            
            # Send any unread announcements first
            unread_announcements = get_user_announcements(user_id, unread_only=True, limit=10)
            for announcement in unread_announcements:
                yield f"data: {json.dumps(announcement)}\n\n"
                time.sleep(0.1)  # Small delay between messages
            
            # Listen for new announcements with timeout and heartbeat
            while True:
                try:
                    message = pubsub.get_message(timeout=5)
                    if message and message["type"] == "message":
                        try:
                            announcement_data = json.loads(message["data"])
                            target_users = announcement_data.get("target_users", "all")
                            if target_users == "all" or (isinstance(target_users, list) and user_id in target_users):
                                announcement_data["is_read"] = False
                                announcement_data["delivered_at"] = datetime.now().isoformat()
                                yield f"data: {json.dumps(announcement_data)}\n\n"
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                    else:
                        # Send heartbeat every 15 seconds
                        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
                        time.sleep(15)
                except Exception as e:
                    logger.error(f"Error in event stream loop: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break
                    
        except GeneratorExit:
            # Clean up on client disconnect
            logger.info(f"Client disconnected from stream for user {user_id}")
            if 'pubsub' in locals():
                pubsub.close()
        except Exception as e:
            logger.error(f"Error in event stream: {e}")
            yield f"data: {json.dumps({'error': 'Stream error occurred'})}\n\n"
    
    return Response(event_stream(), mimetype='text/event-stream', headers=headers)

@app.route("/announcements/stats")
def get_announcement_stats():
    """Get announcement statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database unavailable"}), 500
            
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Total announcements
            cur.execute("SELECT COUNT(*) as total FROM announcements")
            total = cur.fetchone()['total']
            
            # Active announcements (not expired)
            cur.execute("""
                SELECT COUNT(*) as active 
                FROM announcements 
                WHERE expires_at IS NULL OR expires_at > NOW()
            """)
            active = cur.fetchone()['active']
            
            # Read/unread stats
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN read_at IS NOT NULL THEN 1 END) as read,
                    COUNT(CASE WHEN read_at IS NULL THEN 1 END) as unread
                FROM user_announcements ua
                JOIN announcements a ON ua.announcement_id = a.id
                WHERE a.expires_at IS NULL OR a.expires_at > NOW()
            """)
            read_stats = cur.fetchone()
            
        conn.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_announcements": total,
                "active_announcements": active,
                "read_deliveries": read_stats['read']
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to get statistics"
        }), 500

@app.route("/announcements/<int:user_id>")
def get_announcements(user_id):
    """Get all announcements for a user"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Database connection failed"}), 500
            
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT a.*, ua.read_at, ua.created_at as delivered_at,
                       u.name as created_by_name
                FROM announcements a
                JOIN user_announcements ua ON a.id = ua.announcement_id
                LEFT JOIN users u ON a.created_by = u.id
                WHERE ua.user_id = %s
                ORDER BY a.created_at DESC
            """, (user_id,))
            
            announcements = cur.fetchall()
            conn.close()
            
            return jsonify({
                "success": True,
                "data": [{
                    'id': ann['id'],
                    'title': ann['title'],
                    'message': ann['message'],
                    'type': ann['announcement_type'],
                    'priority': ann['priority'],
                    'created_at': ann['created_at'].isoformat(),
                    'expires_at': ann['expires_at'].isoformat() if ann['expires_at'] else None,
                    'delivered_at': ann['delivered_at'].isoformat() if ann['delivered_at'] else None,
                    'read_at': ann['read_at'].isoformat() if ann['read_at'] else None,
                    'created_by_name': ann['created_by_name'],
                    'is_read': ann['read_at'] is not None
                } for ann in announcements]
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting announcements for user {user_id}: {e}")
        return jsonify({"success": False, "error": "Failed to get announcements"}), 500

@app.route("/health")
def health_check():
    """Health check endpoint"""
    redis_status = "ok" if r and r.ping() else "error"
    db_status = "ok" if get_db_connection() else "error"
    
    return jsonify({
        "status": "ok",
        "service": "announcements",
        "redis": redis_status,
        "database": db_status
    })

@app.after_request
def after_request(response):
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.add('Access-Control-Expose-Headers', '*')
    return response

def init_database():
    """Initialize database tables with retries"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            # Create users table first
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    role VARCHAR(20) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    phone VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Then create announcements tables
            cur.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    announcement_type VARCHAR(50) DEFAULT 'general',
                    target_users TEXT,
                    priority VARCHAR(20) DEFAULT 'normal',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    created_by INTEGER REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS user_announcements (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    announcement_id INTEGER REFERENCES announcements(id),
                    read_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Insert test user if not exists
            cur.execute("""
                INSERT INTO users (role, name, email, password_hash, phone)
                SELECT 'admin', 'Admin User', 'admin@example.com', 'hash123', '123-456-7890'
                WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'admin@example.com');
            """)
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        if conn:
            conn.close()
        return False

# Initialize database on startup
@app.before_first_request
def initialize():
    """Initialize database tables"""
    if not init_announcements_table():
        logger.error("Failed to initialize announcements table")

if __name__ == "__main__":
    # Initialize database first
    if init_database():
        logger.info("Database initialized successfully")
    else:
        logger.error("Failed to initialize database")

    # Test connections on startup with retry
    conn = get_db_connection()
    if conn:
        logger.info("Database connection successful")
        init_announcements_table()
        conn.close()
    else:
        logger.error("Failed to connect to database")
        
    # Test Redis with retry
    redis_connected = False
    for i in range(5):
        try:
            if r and r.ping():
                logger.info("Redis connection successful")
                redis_connected = True
                break
            time.sleep(2)
        except:
            logger.error(f"Redis connection attempt {i+1} failed")
    
    if not redis_connected:
        logger.error("All Redis connection attempts failed")
            
    app.run(host="0.0.0.0", port=5006, threaded=True, debug=True)