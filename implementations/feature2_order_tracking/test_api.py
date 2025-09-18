import requests
import time

BASE_URL = "http://localhost:5002"

def test_create_order():
    """Create a test order"""
    order_data = {
        "customer_id": 1,
        "restaurant_id": 1,
        "items": [
            {"menu_item_id": 1, "quantity": 2},
            {"menu_item_id": 2, "quantity": 1}
        ]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/orders",
            json=order_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Create Order Response: {response.status_code}")
        print(f"Response Data: {response.text}")
        return response.json().get('order_id') if response.ok else None
    except Exception as e:
        print(f"Error creating order: {e}")
        return None

def test_track_order(order_id):
    """Test SSE order tracking"""
    try:
        response = requests.get(
            f"{BASE_URL}/orders/{order_id}/status/stream",
            stream=True,
            headers={'Accept': 'text/event-stream'}
        )
        
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f"Order Update: {line}")
                
    except Exception as e:
        print(f"Error tracking order: {e}")

def main():
    print("=== Testing Order Tracking ===")
    
    # Test health
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health check: {response.status_code} - {response.json()}")
    
    # Create test order
    order_id = test_create_order()
    if order_id:
        print(f"Created order ID: {order_id}")
        # Track the order
        test_track_order(order_id)
    else:
        print("Failed to create test order")

if __name__ == "__main__":
    main()
