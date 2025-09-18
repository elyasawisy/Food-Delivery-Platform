from flask import Flask, request, jsonify, Response
import psycopg2
import psycopg2.extras
import json
import os
import time
import threading
from datetime import datetime
import logging

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'foodfast_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'port': os.getenv('DB_PORT', '5432')
}

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for SSE connections (in production, use Redis)
active_connections = {}

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def validate_customer(customer_id):
    """Validate if customer exists"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE id = %s AND role = 'customer'", (customer_id,))
            result = cur.fetchone()
            conn.close()
            return result is not None
    except Exception as e:
        logger.error(f"Error validating customer: {e}")
        if conn:
            conn.close()
        return False

def validate_restaurant(restaurant_id):
    """Validate if restaurant exists"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM restaurants WHERE id = %s", (restaurant_id,))
            result = cur.fetchone()
            conn.close()
            return result is not None
    except Exception as e:
        logger.error(f"Error validating restaurant: {e}")
        if conn:
            conn.close()
        return False

def validate_menu_items(items):
    """Validate menu items exist"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            menu_item_ids = [item['menu_item_id'] for item in items]
            cur.execute("""
                SELECT id FROM menu_items WHERE id = ANY(%s)
            """, (menu_item_ids,))
            
            existing_ids = [row[0] for row in cur.fetchall()]
            conn.close()
            
            return len(existing_ids) == len(menu_item_ids)
    except Exception as e:
        logger.error(f"Error validating menu items: {e}")
        if conn:
            conn.close()
        return False

def create_order(customer_id, restaurant_id, items):
    """Create new order in database"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor() as cur:
            # Create order
            cur.execute("""
                INSERT INTO orders (customer_id, restaurant_id, status, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (customer_id, restaurant_id, 'confirmed', datetime.now()))
            
            order_id = cur.fetchone()[0]
            
            # Add order items
            for item in items:
                cur.execute("""
                    INSERT INTO order_items (order_id, menu_item_id, quantity)
                    VALUES (%s, %s, %s)
                """, (order_id, item['menu_item_id'], item['quantity']))
            
            conn.commit()
            conn.close()
            return order_id
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None

def get_order_details(order_id):
    """Get order details with items"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get order details
            cur.execute("""
                SELECT o.*, u.name as customer_name, r.name as restaurant_name
                FROM orders o
                LEFT JOIN users u ON o.customer_id = u.id
                LEFT JOIN restaurants r ON o.restaurant_id = r.id
                WHERE o.id = %s
            """, (order_id,))
            
            order = cur.fetchone()
            if not order:
                conn.close()
                return None
            
            # Get order items
            cur.execute("""
                SELECT oi.*, mi.name as item_name, mi.price
                FROM order_items oi
                LEFT JOIN menu_items mi ON oi.menu_item_id = mi.id
                WHERE oi.order_id = %s
            """, (order_id,))
            
            items = cur.fetchall()
            conn.close()
            
            return {
                'id': order['id'],
                'customer_id': order['customer_id'],
                'customer_name': order['customer_name'],
                'restaurant_id': order['restaurant_id'],
                'restaurant_name': order['restaurant_name'],
                'status': order['status'],
                'created_at': order['created_at'].isoformat(),
                'items': [{
                    'menu_item_id': item['menu_item_id'],
                    'name': item['item_name'],
                    'price': float(item['price']) if item['price'] else 0,
                    'quantity': item['quantity']
                } for item in items]
            }
            
    except Exception as e:
        logger.error(f"Error getting order details: {e}")
        if conn:
            conn.close()
        return None

def update_order_status(order_id, status):
    """Update order status in database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE orders SET status = %s WHERE id = %s
            """, (status, order_id))
            
            conn.commit()
            conn.close()
            
            # Notify SSE connections
            notify_order_update(order_id, status)
            return True
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        if conn:
            conn.close()
        return False

def notify_order_update(order_id, status):
    """Notify all SSE connections about order update"""
    if order_id in active_connections:
        order_details = get_order_details(order_id)
        update_data = {
            'order_id': order_id,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'order_details': order_details
        }
        
        # Store update for SSE streaming
        if order_id not in active_connections:
            active_connections[order_id] = []
        active_connections[order_id].append(update_data)

def simulate_order_progress(order_id):
    """Simulate order status progression"""
    def progress():
        statuses = [
            ('confirmed', 2),
            ('preparing', 10),
            ('ready', 5),
            ('picked_up', 8),
            ('delivered', 0)
        ]
        
        for status, wait_time in statuses:
            time.sleep(wait_time)
            update_order_status(order_id, status)
            logger.info(f"Order {order_id} status updated to: {status}")
    
    # Run in background thread
    thread = threading.Thread(target=progress)
    thread.daemon = True
    thread.start()

@app.route("/orders", methods=["POST"])
def create_order_endpoint():
    """Create a new order"""
    try:
        data = request.get_json()
        
        # Validate input
        customer_id = data.get('customer_id')
        restaurant_id = data.get('restaurant_id')
        items = data.get('items', [])
        
        if not all([customer_id, restaurant_id, items]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: customer_id, restaurant_id, items'
            }), 400
        
        # Validate customer exists
        if not validate_customer(customer_id):
            return jsonify({
                'success': False,
                'error': 'Invalid customer ID'
            }), 400
        
        # Validate restaurant exists
        if not validate_restaurant(restaurant_id):
            return jsonify({
                'success': False,
                'error': 'Invalid restaurant ID'
            }), 400
        
        # Validate items format
        for item in items:
            if not all(key in item for key in ['menu_item_id', 'quantity']):
                return jsonify({
                    'success': False,
                    'error': 'Invalid item format. Each item must have menu_item_id and quantity'
                }), 400
            
            if item['quantity'] <= 0:
                return jsonify({
                    'success': False,
                    'error': 'Item quantity must be greater than 0'
                }), 400
        
        # Validate menu items exist
        if not validate_menu_items(items):
            return jsonify({
                'success': False,
                'error': 'One or more menu items not found'
            }), 400
        
        # Create order
        order_id = create_order(customer_id, restaurant_id, items)
        if not order_id:
            return jsonify({
                'success': False,
                'error': 'Failed to create order'
            }), 500
        
        # Initialize tracking for this order
        active_connections[order_id] = []
        
        # Start order progression simulation
        simulate_order_progress(order_id)
        
        # Get order details
        order_details = get_order_details(order_id)
        
        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': 'Order created successfully',
            'order_details': order_details
        }), 201
        
    except Exception as e:
        logger.error(f"Error in create order endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route("/orders/<int:order_id>/status/stream")
def stream_order_status(order_id):
    """SSE endpoint for order status updates"""
    
    # Validate order exists
    order_details = get_order_details(order_id)
    if not order_details:
        return jsonify({'error': 'Order not found'}), 404
    
    def event_stream():
        try:
            # Send initial order status
            yield f"event: status_update\n"
            yield f"data: {json.dumps(order_details)}\n\n"
            
            # Initialize connection tracking
            if order_id not in active_connections:
                active_connections[order_id] = []
            
            last_update_count = 0
            
            # Keep connection alive and send updates
            while True:
                current_updates = active_connections.get(order_id, [])
                
                # Send new updates
                if len(current_updates) > last_update_count:
                    for update in current_updates[last_update_count:]:
                        yield f"event: status_update\n"
                        yield f"data: {json.dumps(update)}\n\n"
                        
                        # Close connection if order is delivered
                        if update['status'] == 'delivered':
                            yield f"event: complete\n"
                            yield f"data: {json.dumps({'message': 'Order delivered successfully'})}\n\n"
                            return
                    
                    last_update_count = len(current_updates)
                
                # Send heartbeat every 30 seconds
                yield f"event: heartbeat\n"
                yield f"data: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"
                
                time.sleep(5)  # Check for updates every 5 seconds
                
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': 'Stream error occurred'})}\n\n"
    
    response = Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type"
        }
    )
    
    return response

@app.route("/orders/<int:order_id>")
def get_order(order_id):
    """Get order details"""
    order_details = get_order_details(order_id)
    if not order_details:
        return jsonify({'error': 'Order not found'}), 404
    
    return jsonify({
        'success': True,
        'order': order_details
    })

@app.route("/orders/<int:order_id>/status", methods=["PUT"])
def update_order_status_endpoint(order_id):
    """Update order status (for testing)"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        valid_statuses = ['confirmed', 'preparing', 'ready', 'picked_up', 'delivered']
        if status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400
        
        success = update_order_status(order_id, status)
        if success:
            return jsonify({
                'success': True,
                'message': f'Order status updated to {status}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update order status'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route("/orders")
def list_orders():
    """List all orders (for testing)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database unavailable'}), 500
            
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT o.*, u.name as customer_name, r.name as restaurant_name
                FROM orders o
                LEFT JOIN users u ON o.customer_id = u.id
                LEFT JOIN restaurants r ON o.restaurant_id = r.id
                ORDER BY o.created_at DESC
                LIMIT 20
            """)
            
            orders = cur.fetchall()
            
        conn.close()
        
        return jsonify({
            'success': True,
            'orders': [{
                'id': order['id'],
                'customer_name': order['customer_name'],
                'restaurant_name': order['restaurant_name'],
                'status': order['status'],
                'created_at': order['created_at'].isoformat()
            } for order in orders]
        })
        
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to list orders'
        }), 500

@app.route("/health")
def health():
    """Health check endpoint"""
    db_status = "ok" if get_db_connection() else "error"
    
    return jsonify({
        "status": "ok",
        "service": "order_tracking",
        "database": db_status
    })

if __name__ == "__main__":
    # Test database connection on startup
    conn = get_db_connection()
    if conn:
        logger.info("Database connection successful")
        conn.close()
    else:
        logger.error("Failed to connect to database")
    
    app.run(host="0.0.0.0", port=5002, threaded=True, debug=True)