import requests
import json
import threading
import time

BASE_URL = "http://localhost:5004"

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f" Health check failed: {e}")
        return False

def create_test_restaurant():
    """Create a test restaurant"""
    restaurant_data = {
        "name": "Pizza Palace",
        "address": "123 Main St, Nablus",
        "phone": "+970-9-123-4567"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/restaurants",
            json=restaurant_data,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 201:
            restaurant_id = response.json()['restaurant_id']
            print(f" Created restaurant: {restaurant_id}")
            return restaurant_id
        else:
            print(f" Failed to create restaurant: {response.text}")
            return None
    except Exception as e:
        print(f" Restaurant creation failed: {e}")
        return None

def test_place_order(restaurant_id):
    """Test placing an order"""
    order_data = {
        "restaurant_id": restaurant_id,
        "customer_id": 1,
        "items": [
            {"menu_item_id": 1, "quantity": 2},
            {"menu_item_id": 2, "quantity": 1}
        ]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/place_order",
            json=order_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [201]:
            result = response.json()
            print(f" Order placed: {result}")
            return result.get('order_id')
        else:
            print(f" Failed to place order: {response.text}")
            return None
    except Exception as e:
        print(f" Order placement failed: {e}")
        return None

def test_get_orders(restaurant_id):
    """Test getting restaurant orders via REST"""
    try:
        response = requests.get(f"{BASE_URL}/restaurant/{restaurant_id}/orders")
        if response.status_code == 200:
            result = response.json()
            print(f" Restaurant orders: {len(result['orders'])} orders found")
            return True
        else:
            print(f" Failed to get orders: {response.text}")
            return False
    except Exception as e:
        print(f" Get orders failed: {e}")
        return False

def test_sse_stream(restaurant_id):
    """Test SSE stream for restaurant notifications"""
    print(f" Starting SSE stream for restaurant {restaurant_id}...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/restaurant/{restaurant_id}/orders/stream",
            stream=True,
            headers={'Accept': 'text/event-stream'},
            timeout=30  # 30 second timeout
        )
        
        if response.status_code != 200:
            print(f" SSE stream failed to start: {response.text}")
            return
        
        event_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f" SSE: {line}")
                event_count += 1
                
                # Stop after receiving a few events or on specific events
                if "new_order" in line or event_count > 10:
                    print(" Received order notification!")
                    break
                    
        print(f" SSE stream ended after {event_count} events")
        
    except requests.exceptions.Timeout:
        print(" SSE stream timeout (normal for testing)")
    except KeyboardInterrupt:
        print(" SSE stream stopped by user")
    except Exception as e:
        print(f" SSE stream error: {e}")

def simulate_multiple_orders(restaurant_id):
    """Simulate multiple orders being placed"""
    print(f" Simulating multiple orders for restaurant {restaurant_id}")
    
    orders = [
        {
            "customer_id": 1,
            "items": [{"menu_item_id": 1, "quantity": 1}]
        },
        {
            "customer_id": 2,
            "items": [{"menu_item_id": 2, "quantity": 2}, {"menu_item_id": 3, "quantity": 1}]
        },
        {
            "customer_id": 3,
            "items": [{"menu_item_id": 1, "quantity": 3}]
        }
    ]
    
    time.sleep(3)  # Wait for SSE stream to start
    
    for i, order in enumerate(orders):
        order["restaurant_id"] = restaurant_id
        print(f" Placing order {i+1}/3...")
        
        order_id = test_place_order(restaurant_id)
        if order_id:
            print(f"    Order {order_id} placed successfully")
        else:
            print(f"    Order {i+1} failed")
        
        time.sleep(5)  # Wait between orders

def main():
    print("=== Testing Feature 4: Restaurant Notifications (Pub/Sub + SSE) ===\n")
    
    # Test health first
    if not test_health():
        print(" Health check failed, stopping tests")
        return
    
    # Create test restaurant
    restaurant_id = create_test_restaurant()
    if not restaurant_id:
        print(" Cannot create restaurant, using restaurant_id=1")
        restaurant_id = 1
    
    # Test getting orders (should be empty initially)
    print("\n--- Testing REST API ---")
    test_get_orders(restaurant_id)
    
    # Start SSE stream in background
    print("\n--- Testing SSE Stream ---")
    sse_thread = threading.Thread(
        target=test_sse_stream,
        args=(restaurant_id,)
    )
    sse_thread.daemon = True
    sse_thread.start()
    
    # Wait a moment for SSE to connect
    time.sleep(2)
    
    # Start simulating orders
    print("\n--- Simulating Orders ---")
    simulate_multiple_orders(restaurant_id)
    
    # Wait for SSE thread to complete
    sse_thread.join(timeout=10)
    
    # Test getting orders again (should have orders now)
    print("\n--- Final Orders Check ---")
    test_get_orders(restaurant_id)
    
    print("\n Feature 4 tests completed!")
    print("\n To test properly:")
    print("   1. Make sure Redis is running and accessible")
    print("   2. Make sure PostgreSQL has the required tables")
    print("   3. Open browser and navigate to the SSE endpoint manually")
    print("   4. Place orders through the REST API and watch them appear")

if __name__ == "__main__":
    main()