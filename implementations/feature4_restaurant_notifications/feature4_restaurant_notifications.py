from flask import Flask, Response, request, jsonify
import redis
import threading
import time
import os

app = Flask(__name__)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL)

# Initialize Redis
def publish_order(order_data):
    r.publish("new_orders", order_data)

# Endpoint for placing a new order
@app.route("/place_order", methods=["POST"])
def place_order():
    order_data = request.json
    r.publish("new_orders", str(order_data))
    return jsonify({"status": "order published"})

# Endpoint for restaurants to stream new orders
@app.route("/restaurant/<int:restaurant_id>/orders/stream")
def stream_orders(restaurant_id):
    def event_stream():
        pubsub = r.pubsub()
        pubsub.subscribe("new_orders")
        for message in pubsub.listen():
            if message["type"] == "message":
                yield f"data: {message['data'].decode()}\n\n"
    return Response(event_stream(), mimetype="text/event-stream")

# Health check endpoint
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)