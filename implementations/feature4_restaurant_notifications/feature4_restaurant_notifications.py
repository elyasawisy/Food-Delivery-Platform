from flask import Flask, Response, request, jsonify
import redis
import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime
import threading
import time
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PostgreSQL configuration
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),  # Changed from 'postgres'
    'user': os.getenv('DB_USER', 'foodfast'),
    'password': os.getenv('DB_PASSWORD', 'foodfast123'),
    'database': os.getenv('DB_NAME', 'foodfast_db'),
    'port': int(os.getenv('DB_PORT', 5432))
}

def get_db_connection():
    """Create database connection with retries"""
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting database connection (attempt {attempt + 1}/{max_retries})")
            logger.info(f"Connection params: host={db_config['host']}, port={db_config['port']}, db={db_config['database']}")
            conn = psycopg2.connect(**db_config)
            logger.info(f"Successfully connected to database on attempt {attempt + 1}")
            return conn
        except psycopg2.Error as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    logger.error("All database connection attempts failed")
    return None

# Initialize Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")  # Changed from redis:6379
try:
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info("Redis connected successfully")
except Exception as e:
    logger.error(f"Redis connection error: {e}")
    r = None    



def validate_restaurant_exists(restaurant_id):
    """  #5: Validate restaurant exists in database"""
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed"
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM restaurants WHERE id = %s", (restaurant_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return bool(result), None if result else "Restaurant not found"
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.close()
        return False, "Database query failed"

def validate_order_data(order_data):
    """  #4: Validate order data structure"""
    required_fields = ['restaurant_id', 'customer_id', 'items']
    
    for field in required_fields:
        if field not in order_data:
            return False, f"Missing required field: {field}"
    
    # Validate items structure
    items = order_data.get('items', [])
    if not isinstance(items, list) or len(items) == 0:
        return False, "Items must be a non-empty array"
    
    for item in items:
        if not isinstance(item, dict) or 'menu_item_id' not in item or 'quantity' not in item:
            return False, "Each item must have menu_item_id and quantity"
        
        try:
            quantity = int(item['quantity'])
            if quantity <= 0:
                return False, "Item quantity must be positive"
        except (ValueError, TypeError):
            return False, "Item quantity must be a valid number"
    
    return True, None

def store_order_in_database(order_data):
    """  #2: Store order in PostgreSQL database"""
    conn = get_db_connection()
    if not conn:
        return None, "Database connection failed"
    
    try:
        cursor = conn.cursor()
        
        # Insert order
        cursor.execute(
            """INSERT INTO orders (customer_id, restaurant_id, status, created_at) 
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (order_data['customer_id'], order_data['restaurant_id'], 'confirmed', datetime.utcnow())
        )
        order_id = cursor.fetchone()[0]
        
        # Insert order items
        for item in order_data['items']:
            cursor.execute(
                """INSERT INTO order_items (order_id, menu_item_id, quantity) 
                   VALUES (%s, %s, %s)""",
                (order_id, item['menu_item_id'], item['quantity'])
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        return order_id, None
        
    except psycopg2.Error as e:
        print(f"Database insert error: {e}")
        conn.rollback()
        if conn:
            conn.close()
        return None, f"Failed to store order: {str(e)}"

# Health check endpoint
@app.route("/health")
def health():
    status = {"flask": "ok"}
    
    # Check database
    conn = get_db_connection()
    if conn:
        status["database"] = "connected"
        conn.close()
    else:
        status["database"] = "disconnected"
    
    # Check Redis
    if r:
        try:
            r.ping()
            status["redis"] = "connected"
        except:
            status["redis"] = "disconnected"
    else:
        status["redis"] = "not_configured"
    
    return jsonify(status), 200

#   #2,#4,#5: Enhanced endpoint for placing orders
@app.route("/place_order", methods=["POST"])
def place_order():
    """Place a new order"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        try:
            # Insert order
            cursor.execute("""
                INSERT INTO orders (customer_id, restaurant_id, status)
                VALUES (%s, %s, 'confirmed')
                RETURNING id
            """, (data["customer_id"], data["restaurant_id"]))
            
            order_id = cursor.fetchone()[0]
            
            # Insert order items
            for item in data["items"]:
                cursor.execute("""
                    INSERT INTO order_items (order_id, menu_item_id, quantity)
                    VALUES (%s, %s, %s)
                """, (order_id, item["menu_item_id"], item["quantity"]))
            
            conn.commit()
            
            # Publish to Redis for real-time notification
            if r:
                notification = {
                    "type": "new_order",
                    "order_id": order_id,
                    "restaurant_id": data["restaurant_id"],
                    "timestamp": datetime.utcnow().isoformat()
                }
                r.publish(f"restaurant:{data['restaurant_id']}", json.dumps(notification))
            
            return jsonify({
                "order_id": order_id,
                "message": "Order placed successfully"
            }), 201
            
        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
            return jsonify({"error": "Database query failed"}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        return jsonify({"error": "Failed to place order"}), 500

#   #3: Enhanced SSE endpoint with proper error handling
@app.route("/restaurant/<int:restaurant_id>/orders/stream")
def stream_orders(restaurant_id):
    """SSE endpoint for restaurant orders"""
    def event_stream():
        if not r:
            yield f"data: {json.dumps({'error': 'Redis not available'})}\n\n"
            return
            
        pubsub = r.pubsub()
        pubsub.subscribe(f"restaurant:{restaurant_id}")
        
        try:
            for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
        except GeneratorExit:
            pubsub.unsubscribe()
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

#   #2: Add endpoint to get restaurant orders (REST fallback)
@app.route("/restaurant/<int:restaurant_id>/orders")
def get_restaurant_orders(restaurant_id):
    """Get restaurant orders"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cursor.execute("""
                SELECT o.*, u.name as customer_name
                FROM orders o
                JOIN users u ON o.customer_id = u.id
                WHERE o.restaurant_id = %s
                ORDER BY o.created_at DESC
                LIMIT 50
            """, (restaurant_id,))
            
            orders = cursor.fetchall()
            return jsonify({
                "orders": [{
                    "id": order["id"],
                    "customer_name": order["customer_name"],
                    "status": order["status"],
                    "created_at": order["created_at"].isoformat()
                } for order in orders]
            })
            
        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            return jsonify({"error": "Database query failed"}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        return jsonify({"error": "Failed to get orders"}), 500

# Add endpoint to create test restaurant (for testing)
@app.route("/restaurants", methods=["POST"])
def create_restaurant():
    """Create a test restaurant"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO restaurants (name, address, phone)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (data.get('name'), data.get('address'), data.get('phone')))
            
            restaurant_id = cursor.fetchone()[0]
            conn.commit()
            
            return jsonify({
                "restaurant_id": restaurant_id,
                "message": "Restaurant created successfully"
            }), 201
            
        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
            return jsonify({"error": "Failed to create restaurant"}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Error creating restaurant: {e}")
        return jsonify({"error": "Failed to create restaurant"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True, threaded=True)