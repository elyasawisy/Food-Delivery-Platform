from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
import redis
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Initialize Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
try:
    r = redis.Redis.from_url(REDIS_URL)
    r.ping()
except Exception as e:
    print(f"Redis connection error: {e}")
    r = None

driver_locations = {}

# Endpoint for drivers to update their location
@app.route("/update_location", methods=["POST"])
def update_location():
    data = request.json
    driver_id = data.get("driver_id")
    order_id = data.get("order_id")
    lat = data.get("lat")
    lng = data.get("lng")

    if not all([driver_id, order_id, lat, lng]):
        return jsonify({"error": "Missing data"}), 400

    # Save latest location in memory and optionally in Redis
    driver_locations[driver_id] = {"lat": lat, "lng": lng}
    if r:
        r.set(f"driver:{driver_id}:location", f"{lat},{lng}")

    # Emit location only to the customer's room
    socketio.emit("driver_location", {"driver_id": driver_id, "lat": lat, "lng": lng},
                  room=f"order_{order_id}")
    return jsonify({"status": "location updated"})

# WebSocket event for customers to join order room
@socketio.on("join_order")
def handle_join_order(data):
    order_id = data.get("order_id")
    driver_id = data.get("driver_id")
    if order_id:
        room = f"order_{order_id}"
        join_room(room)
        print(f"Customer joined room {room}")
        # Send last known location if available
        location = driver_locations.get(driver_id)
        if not location and r and driver_id:
            loc_str = r.get(f"driver:{driver_id}:location")
            if loc_str:
                lat, lng = loc_str.decode().split(",")
                location = {"driver_id": driver_id, "lat": float(lat), "lng": float(lng)}
        if location:
            emit("driver_location", location)
        else:
            emit("driver_location", {"message": "connected"})

# WebSocket event for customers to leave order room
@socketio.on("leave_order")
def handle_leave_order(data):
    order_id = data.get("order_id")
    if order_id:
        leave_room(f"order_{order_id}")
        print(f"Customer left room order_{order_id}")

# Health check endpoint
@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
