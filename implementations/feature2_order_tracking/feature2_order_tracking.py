from flask import Flask, Response, request , jsonify
import psycopg2
import psycopg2.extras
import time
import json
import os

app = Flask(__name__)

# Configure PostgreSQL connection
db_config = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'user': os.getenv('DB_USER', 'foodfast'),
    'password': os.getenv('DB_PASSWORD', 'foodfast123'),
    'database': os.getenv('DB_NAME', 'foodfast_db'),  
    'port': os.getenv('DB_PORT', 5432)
}

# Function to get a database connection
def get_db_connection():
    try:
        return psycopg2.connect(**db_config)
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return None

# Function to fetch order status from the database
def fetch_order_status(order_id):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT status, created_at FROM orders WHERE id = %s", (order_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(result) if result else None
    except psycopg2.Error as e:
        print(f"Error fetching order status: {e}")
        if conn:
            conn.close()
        return None

# Health check endpoint
@app.route('/health')
def health():
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error", "message": "Database connection failed"}), 500


@app.route('/orders/<int:order_id>/status')
def get_order_status(order_id):
    order_data = fetch_order_status(order_id)
    if order_data:
        return jsonify({
            "order_id": order_id,
            "status": order_data["status"],
            "created_at": order_data["created_at"].isoformat() if order_data["created_at"] else None
        }), 200
    else:
        return jsonify({"error": "Order not found"}), 404

# SSE endpoint to stream order status updates 
@app.route('/orders/<int:order_id>/status/stream')
def stream_order_status(order_id):
    # First, check if order exists
    initial_order = fetch_order_status(order_id)
    if not initial_order:
        return jsonify({"error": "Order not found"}), 404

    def event_stream():
        last_status = None
        check_count = 0
        max_checks = 120  
        
        try:
            while check_count < max_checks:
                order_data = fetch_order_status(order_id)
                
                if not order_data:
                    # Order was deleted or error occurred
                    yield f"event: error\ndata: {json.dumps({'error': 'Order not found'})}\n\n"
                    break
                
                current_status = order_data["status"]
                
                #  Send JSON data with proper SSE format
                if current_status != last_status:
                    event_data = {
                        "order_id": order_id,
                        "status": current_status,
                        "timestamp": order_data["created_at"].isoformat() if order_data["created_at"] else None,
                        "check_count": check_count + 1
                    }
                    yield f"event: status_update\ndata: {json.dumps(event_data)}\n\n"
                    last_status = current_status
                    
                    # Stop streaming if order is delivered
                    if current_status in ['delivered', 'cancelled']:
                        yield f"event: complete\ndata: {json.dumps({'message': 'Order tracking complete'})}\n\n"
                        break
                else:
                    # Send heartbeat to keep connection alive
                    yield f"event: heartbeat\ndata: {json.dumps({'order_id': order_id, 'status': current_status})}\n\n"
                
                check_count += 1
                time.sleep(30)  # Check every 30 seconds
                
        except GeneratorExit:
            # Client disconnected
            print(f"Client disconnected from order {order_id} stream")
        except Exception as e:
            print(f"Error in event stream: {e}")
            yield f"event: error\ndata: {json.dumps({'error': 'Stream error occurred'})}\n\n"
    
    #  Proper SSE headers
    return Response(
        event_stream(), 
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True, threaded=True)