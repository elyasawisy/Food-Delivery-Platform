import socketio
import requests
import time
import threading
import json

# Test configuration
BASE_URL = "http://localhost:5003"
SOCKET_URL = "http://localhost:5003"

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f" Health check failed: {e}")
        return False

def create_test_order_with_driver():
    """Create a test order with driver assignment"""
    # This would typically be done through your order management system
    # For testing, we'll assume order_id=1 with driver_id=1 exists
    print(" Using test order_id=1 with driver_id=1")
    print("   (Make sure this order exists in your database with status='picked_up')")
    return 1, 1  # order_id, driver_id

def test_location_update(order_id, driver_id):
    """Test driver location update via REST API"""
    location_data = {
        "driver_id": driver_id,
        "order_id": order_id,
        "lat": 31.7683,  # Nablus coordinates
        "lng": 35.2137
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/update_location",
            json=location_data,
            headers={"Content-Type": "application/json"}
        )
        print(f" Location Update: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f" Location update failed: {e}")
        return False

def test_get_location(order_id):
    """Test getting driver location via REST API"""
    try:
        response = requests.get(f"{BASE_URL}/orders/{order_id}/driver_location")
        print(f" Get Location: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f" Get location failed: {e}")
        return False

def test_websocket_client(order_id, customer_id=1):
    """Test WebSocket connection as customer"""
    print(f" Starting WebSocket client for order {order_id}")
    
    # Create SocketIO client
    sio = socketio.Client()
    
    @sio.event
    def connect():
        print(" WebSocket connected!")
        # Join order room
        sio.emit('join_order', {
            'order_id': order_id,
            'customer_id': customer_id
        })
    
    @sio.event
    def disconnect():
        print(" WebSocket disconnected!")
    
    @sio.on('driver_location')
    def on_driver_location(data):
        print(f" Received driver location: {data}")
    
    @sio.on('connection_status')
    def on_connection_status(data):
        print(f" Connection status: {data}")
    
    @sio.on('error')
    def on_error(data):
        print(f" WebSocket error: {data}")
    
    try:
        # Connect to WebSocket
        sio.connect(SOCKET_URL)
        
        # Keep connection alive for testing
        time.sleep(20)  # Listen for 20 seconds
        
        # Leave room and disconnect
        sio.emit('leave_order', {'order_id': order_id})
        sio.disconnect()
        
    except Exception as e:
        print(f" WebSocket test failed: {e}")

def simulate_driver_movement(order_id, driver_id):
    """Simulate driver moving with location updates"""
    print(f" Simulating driver {driver_id} movement for order {order_id}")
    
    # Simulate movement around Nablus
    locations = [
        {"lat": 31.7683, "lng": 35.2137, "name": "Starting point"},
        {"lat": 31.7703, "lng": 35.2157, "name": "Moving north"},
        {"lat": 31.7723, "lng": 35.2177, "name": "Further north"},
        {"lat": 31.7743, "lng": 35.2197, "name": "Near destination"},
        {"lat": 31.7763, "lng": 35.2217, "name": "Delivered"}
    ]
    
    for i, location in enumerate(locations):
        print(f" Driver at: {location['name']} ({location['lat']}, {location['lng']})")
        
        location_data = {
            "driver_id": driver_id,
            "order_id": order_id,
            "lat": location["lat"],
            "lng": location["lng"]
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/update_location",
                json=location_data,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                print(f"    Location {i+1}/5 updated successfully")
            else:
                print(f"    Failed to update location: {response.text}")
        except Exception as e:
            print(f"    Error updating location: {e}")
        
        time.sleep(5)  # Wait 5 seconds between updates

def main():
    print("=== Testing Feature 3: Driver Location Tracking (WebSocket) ===\n")
    
    # Test health first
    if not test_health():
        print(" Health check failed, stopping tests")
        return
    
    # Get test order and driver
    order_id, driver_id = create_test_order_with_driver()
    
    # Test initial location update
    print("\n--- Testing REST API ---")
    if not test_location_update(order_id, driver_id):
        print(" Location update failed, but continuing...")
    
    # Test getting location
    test_get_location(order_id)
    
    # Start WebSocket client in background
    print("\n--- Testing WebSocket Connection ---")
    websocket_thread = threading.Thread(
        target=test_websocket_client,
        args=(order_id,)
    )
    websocket_thread.daemon = True
    websocket_thread.start()
    
    # Wait a moment for WebSocket to connect
    time.sleep(2)
    
    # Start driver movement simulation
    print("\n--- Simulating Driver Movement ---")
    simulate_driver_movement(order_id, driver_id)
    
    # Wait for WebSocket thread to complete
    websocket_thread.join(timeout=5)
    
    print("\n Feature 3 tests completed!")
    print("\n To test properly:")
    print("   1. Make sure you have an order with id=1 in your database")
    print("   2. Make sure the order has driver_id=1 assigned")
    print("   3. Make sure the order status is 'picked_up'")
    print("   4. Open browser console and connect to WebSocket manually")

if __name__ == "__main__":
    main()