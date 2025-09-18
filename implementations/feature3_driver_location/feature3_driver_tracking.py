from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
import redis
import os
import psycopg2
import psycopg2.extras
import json
from datetime import datetime
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'ely0s123456')

# Initialize SocketIO with eventlet
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True
)

#   #2: PostgreSQL configuration
db_config = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'user': os.getenv('DB_USER', 'foodfast'),
    'password': os.getenv('DB_PASSWORD', 'foodfast123'),
    'database': os.getenv('DB_NAME', 'foodfast_db'),  
    'port': os.getenv('DB_PORT', 5432)
}

def get_db_connection():
    """Create database connection with error handling"""
    try:
        return psycopg2.connect(**db_config)
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None

#   #1: Initialize Redis with better error handling
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
try:
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    print(" Redis connected successfully")
except Exception as e:
    print(f" Redis connection error: {e}")
    r = None

# In-memory fallback for driver locations
driver_locations = {}

def validate_coordinates(lat, lng):
    """  #3: Validate latitude and longitude"""
    try:
        lat = float(lat)
        lng = float(lng)
        
        # Valid coordinate ranges
        if not (-90 <= lat <= 90):
            return None, "Invalid latitude: must be between -90 and 90"
        if not (-180 <= lng <= 180):
            return None, "Invalid longitude: must be between -180 and 180"
            
        return (lat, lng), None
    except (ValueError, TypeError):
        return None, "Coordinates must be valid numbers"

def verify_order_and_driver(order_id, driver_id):
    """  #2: Verify order exists and driver is assigned"""
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed"
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            "SELECT customer_id, driver_id, status FROM orders WHERE id = %s",
            (order_id,)
        )
        order = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not order:
            return False, "Order not found"
        
        if order['driver_id'] != driver_id:
            return False, "Driver not assigned to this order"
            
        if order['status'] not in ['picked_up']:  # Only track during delivery
            return False, f"Order status '{order['status']}' doesn't require tracking"
            
        return True, None
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.close()
        return False, "Database query failed"

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

#   #2,#3: Enhanced endpoint for drivers to update location
@app.route("/update_location", methods=["POST"])
def update_location():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        driver_id = data.get("driver_id")
        order_id = data.get("order_id")
        lat = data.get("lat")
        lng = data.get("lng")

        #   #3: Validate required fields
        if not all([driver_id, order_id, lat is not None, lng is not None]):
            return jsonify({
                "error": "Missing required fields: driver_id, order_id, lat, lng"
            }), 400

        #   #3: Validate coordinate format
        coords, error = validate_coordinates(lat, lng)
        if error:
            return jsonify({"error": error}), 400
        
        lat, lng = coords

        #   #2: Verify order and driver relationship
        is_valid, error = verify_order_and_driver(order_id, driver_id)
        if not is_valid:
            return jsonify({"error": error}), 403

        # Create location data
        location_data = {
            "driver_id": driver_id,
            "order_id": order_id,
            "lat": lat,
            "lng": lng,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Save location in memory
        driver_locations[f"{driver_id}_{order_id}"] = location_data

        #   #1: Save to Redis with error handling
        if r:
            try:
                r.setex(
                    f"driver:{driver_id}:order:{order_id}:location",
                    3600,  # 1 hour expiry
                    json.dumps(location_data)
                )
            except Exception as e:
                print(f"Redis save error: {e}")

        #   #4: Emit to specific order room only
        room = f"order_{order_id}"
        socketio.emit("driver_location", location_data, room=room)
        
        print(f" Driver {driver_id} location updated for order {order_id}: ({lat}, {lng})")
        
        return jsonify({
            "status": "location updated",
            "driver_id": driver_id,
            "order_id": order_id,
            "coordinates": {"lat": lat, "lng": lng}
        }), 200

    except Exception as e:
        print(f"Update location error: {e}")
        return jsonify({"error": "Internal server error"}), 500

#   #4: Enhanced WebSocket event for customers to join order room
@socketio.on("join_order")
def handle_join_order(data):
    try:
        order_id = data.get("order_id")
        customer_id = data.get("customer_id")  #   #4: Add customer verification
        
        if not order_id:
            emit("error", {"message": "Order ID required"})
            return

        #   #2: Verify customer owns this order
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute(
                    "SELECT customer_id, driver_id, status FROM orders WHERE id = %s",
                    (order_id,)
                )
                order = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if not order:
                    emit("error", {"message": "Order not found"})
                    return
                
                # Basic customer verification (in real app, use proper auth)
                if customer_id and order['customer_id'] != customer_id:
                    emit("error", {"message": "Unauthorized"})
                    return
                    
                driver_id = order['driver_id']
                
            except psycopg2.Error as e:
                print(f"Database error in join_order: {e}")
                emit("error", {"message": "Database error"})
                return
        else:
            emit("error", {"message": "Database connection failed"})
            return

        # Join the room
        room = f"order_{order_id}"
        join_room(room)
        print(f"👤 Customer joined room {room}")
        
        # Send last known location if available
        location_key = f"{driver_id}_{order_id}"
        location = driver_locations.get(location_key)
        
        #   #1: Try Redis if not in memory
        if not location and r and driver_id:
            try:
                redis_key = f"driver:{driver_id}:order:{order_id}:location"
                location_str = r.get(redis_key)
                if location_str:
                    location = json.loads(location_str)
            except Exception as e:
                print(f"Redis get error: {e}")
        
        if location:
            emit("driver_location", location)
            emit("connection_status", {"status": "connected", "message": "Tracking driver location"})
        else:
            emit("connection_status", {"status": "connected", "message": "Waiting for driver location"})
            
    except Exception as e:
        print(f"Join order error: {e}")
        emit("error", {"message": "Failed to join order tracking"})

# WebSocket event for customers to leave order room
@socketio.on("leave_order")
def handle_leave_order(data):
    try:
        order_id = data.get("order_id")
        if order_id:
            room = f"order_{order_id}"
            leave_room(room)
            print(f"👤 Customer left room {room}")
            emit("connection_status", {"status": "disconnected"})
    except Exception as e:
        print(f"Leave order error: {e}")

#   #4: Add connection and disconnection handlers
@socketio.on("connect")
def handle_connect():
    print(f" Client connected: {request.sid}")
    emit("connection_status", {"status": "connected"})

@socketio.on("disconnect")
def handle_disconnect():
    print(f" Client disconnected: {request.sid}")

#   #2: Add endpoint to get current driver location (REST fallback)
@app.route("/orders/<int:order_id>/driver_location")
def get_driver_location(order_id):
    try:
        # Get order details
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            "SELECT driver_id, status FROM orders WHERE id = %s",
            (order_id,)
        )
        order = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not order:
            return jsonify({"error": "Order not found"}), 404
        
        if not order['driver_id']:
            return jsonify({"error": "No driver assigned"}), 404
            
        driver_id = order['driver_id']
        
        # Get location
        location_key = f"{driver_id}_{order_id}"
        location = driver_locations.get(location_key)
        
        if not location and r:
            try:
                redis_key = f"driver:{driver_id}:order:{order_id}:location"
                location_str = r.get(redis_key)
                if location_str:
                    location = json.loads(location_str)
            except Exception as e:
                print(f"Redis get error: {e}")
        
        if location:
            return jsonify(location), 200
        else:
            return jsonify({"message": "Driver location not available"}), 404
            
    except Exception as e:
        print(f"Get driver location error: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    # Test connections on startup
    print("Testing database connection...")
    conn = get_db_connection()
    if conn:
        print("Database connection successful")
        conn.close()
    else:
        print("Failed to connect to database")
    
    # Test Redis connection
    if r:
        print("Redis connection successful")
    else:
        print("Redis connection failed")
    
    socketio.run(app, host="0.0.0.0", port=5003, debug=True)