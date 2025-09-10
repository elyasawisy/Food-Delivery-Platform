from flask import Flask, Response, request
import psycopg2
import psycopg2.extras
import time

app = Flask(__name__)

# Configure PostgreSQL connection
db_config = {
    'host': 'postgres',  # use service name, not localhost
    'user': 'foodfast',
    'password': 'foodfast123',
    'dbname': 'foodfast_db'
}

# Function to get a database connection
def get_db_connection():
    return psycopg2.connect(**db_config)

# Function to fetch order status from the database
def fetch_order_status(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result["status"] if result else None

# SSE endpoint to stream order status updates
@app.route('/orders/<int:order_id>/status/stream')
def stream_order_status(order_id):
    def event_stream():
        last_status = None
        while True:
            status = fetch_order_status(order_id)
            if status != last_status:
                yield f"data: {status}\n\n"
                last_status = status
            time.sleep(30)  # Check every 30 seconds (adjust as needed)
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True, threaded=True)