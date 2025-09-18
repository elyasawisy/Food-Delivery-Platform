import requests
import json
import time
import threading

BASE_URL = "http://localhost:5002"

def test_health_check():
    """Test service health"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Health Check: {response.status_code}")
        if response.ok:
            data = response.json()
            print(f"Service Status: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"Health check failed: {response.text}")
            return False
    except Exception as e:
        print(f"Health check error: {e}")
        return False

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
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    try:
        print("Creating test order...")
        response = requests.post(
            f"{BASE_URL}/orders",
            headers=headers,
            json=order_data,
            timeout=10
        )

        print(f"Create Order Response: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"Order created successfully:")
            print(json.dumps(data, indent=2))
            return data.get('order_id')
        else:
            print(f"Failed to create order: {response.text}")
            return None
    except Exception as e:
        print(f"Error creating order: {e}")
        return None

def test_track_order(order_id):
    """Test SSE order tracking"""
    if not order_id:
        print("No order ID to track")
        return

    print(f"\n=== Starting to track order {order_id} ===")
    
    try:
        response = requests.get(
            f"{BASE_URL}/orders/{order_id}/status/stream",
            stream=True,
            headers={'Accept': 'text/event-stream'},
            timeout=60
        )

        if not response.ok:
            print(f"Failed to start tracking: {response.status_code} - {response.text}")
            return

        print("SSE Connection established. Listening for updates...")
        
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f"Received: {line}")
                
                # Parse SSE events
                if line.startswith('event:'):
                    event_type = line.split(':', 1)[1].strip()
                    print(f"Event Type: {event_type}")
                elif line.startswith('data:'):
                    data_json = line.split(':', 1)[1].strip()
                    try:
                        data = json.loads(data_json)
                        
                        if 'status' in data:
                            status = data['status']
                            timestamp = data.get('timestamp', 'Unknown time')
                            print(f" Order Status Update: {status.upper()} at {timestamp}")
                            
                            if status == 'delivered':
                                print(" Order delivered! Stopping tracking.")
                                break
                        elif 'order_details' in data:
                            details = data['order_details']
                            print(f" Order Details:")
                            print(f"   Customer: {details.get('customer_name', 'Unknown')}")
                            print(f"   Restaurant: {details.get('restaurant_name', 'Unknown')}")
                            print(f"   Status: {details.get('status', 'Unknown')}")
                            print(f"   Items: {len(details.get('items', []))} items")
                        elif 'message' in data:
                            print(f" Message: {data['message']}")
                        elif 'error' in data:
                            print(f" Error: {data['error']}")
                            break
                            
                    except json.JSONDecodeError:
                        print(f"Non-JSON data: {data_json}")
                        
    except KeyboardInterrupt:
        print("\n⏹️  Tracking stopped by user")
    except requests.exceptions.Timeout:
        print("\n Connection timed out")
    except Exception as e:
        print(f"\n Error tracking order: {e}")

def test_get_order(order_id):
    """Test getting order details"""
    if not order_id:
        print("No order ID provided")
        return
        
    try:
        response = requests.get(f"{BASE_URL}/orders/{order_id}")
        print(f"Get Order Response: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print("Order Details:")
            print(json.dumps(data, indent=2))
        else:
            print(f"Failed to get order: {response.text}")
            
    except Exception as e:
        print(f"Error getting order: {e}")

def test_update_order_status(order_id, status):
    """Test manual order status update"""
    if not order_id:
        print("No order ID provided")
        return
        
    try:
        response = requests.put(
            f"{BASE_URL}/orders/{order_id}/status",
            json={"status": status},
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Update Status Response: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"Status updated successfully: {data['message']}")
        else:
            print(f"Failed to update status: {response.text}")
            
    except Exception as e:
        print(f"Error updating status: {e}")

def test_list_orders():
    """Test listing orders"""
    try:
        response = requests.get(f"{BASE_URL}/orders")
        print(f"List Orders Response: {response.status_code}")
        
        if response.ok:
            data = response.json()
            orders = data.get('orders', [])
            print(f"Found {len(orders)} orders:")
            
            for order in orders:
                print(f"  Order #{order['id']}: {order['customer_name']} -> {order['restaurant_name']} [{order['status']}]")
                
        else:
            print(f"Failed to list orders: {response.text}")
            
    except Exception as e:
        print(f"Error listing orders: {e}")

def interactive_tracking_test():
    """Interactive test that simulates manual status updates"""
    print("\n=== Interactive Order Tracking Test ===")
    
    # Create order
    order_id = test_create_order()
    if not order_id:
        return
    
    # Start tracking in background thread
    def background_tracking():
        time.sleep(2)  # Wait a bit before starting
        test_track_order(order_id)
    
    tracking_thread = threading.Thread(target=background_tracking)
    tracking_thread.daemon = True
    tracking_thread.start()
    
    # Manual status updates to simulate real order progression
    statuses = [
        ('confirmed', 3),
        ('preparing', 8),
        ('ready', 3),
        ('picked_up', 5),
        ('delivered', 0)
    ]
    
    print(f"\n🤖 Starting automated status progression for order {order_id}")
    
    for status, wait_time in statuses:
        time.sleep(wait_time)
        print(f"\n Manually updating order to: {status}")
        test_update_order_status(order_id, status)
        
        if status == 'delivered':
            break
    
    # Wait for tracking to complete
    time.sleep(2)
    print("\n Interactive test completed")

def main():
    print("=" * 50)
    print(" FoodFast Order Tracking Test Suite")
    print("=" * 50)
    
    # Test health first
    if not test_health_check():
        print(" Service is not available. Please check if the server is running.")
        return
    
    print("\n" + "=" * 30)
    print("Test Options:")
    print("1. Basic order creation and tracking")
    print("2. Interactive tracking with manual updates")
    print("3. List existing orders")
    print("4. Track specific order ID")
    print("=" * 30)
    
    try:
        choice = input("Choose test (1-4, or press Enter for basic test): ").strip()
        
        if choice == "2":
            interactive_tracking_test()
        elif choice == "3":
            test_list_orders()
        elif choice == "4":
            order_id = input("Enter order ID to track: ").strip()
            if order_id.isdigit():
                test_track_order(int(order_id))
            else:
                print("Invalid order ID")
        else:
            # Basic test (default)
            print("\n Running basic order creation and tracking test...")
            order_id = test_create_order()
            if order_id:
                print(f"\n Getting order details...")
                test_get_order(order_id)
                
                print(f"\n Starting order tracking...")
                test_track_order(order_id)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n Test failed with error: {e}")

if __name__ == "__main__":
    main()