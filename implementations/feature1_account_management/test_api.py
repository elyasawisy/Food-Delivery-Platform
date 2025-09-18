import requests
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure retry strategy
retry_strategy = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)

# Create session with retry strategy
session = requests.Session()
session.mount("http://", adapter)
session.mount("https://", adapter)

# Update the BASE_URL to match the exposed port
BASE_URL = "http://localhost:5001"

def wait_for_service():
    """Wait for service to be available"""
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            response = session.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                print("Service is available")
                return True
        except requests.exceptions.RequestException as e:
            print(f"Waiting for service... Attempt {attempt + 1}/{max_attempts}")
            time.sleep(3)
    return False

def test_health():
    """Test health endpoint"""
    try:
        response = session.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code} - {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Health Check failed: {str(e)}")

def test_user_registration():
    """Test user registration"""
    user_data = {
        "name": "Elyas Awisy",
        "email": "elyas@example.com",
        "password": "securepassword123",
        "role": "customer",
        "phone": "+1234567890"
    }
    
    response = requests.post(
        f"{BASE_URL}/users/register",
        headers={"Content-Type": "application/json"},
        json=user_data
    )
    print(f"User Registration: {response.status_code} - {response.json()}")
    return response.json().get("token") if response.status_code == 201 else None

def test_user_login():
    """Test user login"""
    login_data = {
        "email": "elyas@example.com",
        "password": "securepassword123"
    }
    
    response = requests.post(
        f"{BASE_URL}/users/login",
        headers={"Content-Type": "application/json"},
        json=login_data
    )
    print(f"User Login: {response.status_code} - {response.json()}")
    return response.json().get("token") if response.status_code == 200 else None

def test_get_profile(token):
    """Test get user profile"""
    if not token:
        print("No token available for profile test")
        return
    
    response = requests.get(
        f"{BASE_URL}/users/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"Get Profile: {response.status_code} - {response.json()}")

def test_update_profile(token):
    """Test update user profile"""
    if not token:
        print("No token available for update test")
        return
    
    update_data = {
        "name": "Mohamed Awisy",
        "phone": "+1987654321"
    }
    
    response = requests.put(
        f"{BASE_URL}/users/profile",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=update_data
    )
    print(f"Update Profile: {response.status_code} - {response.json()}")

def test_add_payment_method(token):
    """Test add payment method"""
    if not token:
        print("No token available for payment method test")
        return
    
    payment_data = {
        "card_number": "1234567890123456",
        "card_holder": "Mohamed Awisy",
        "expiry_month": 3,
        "expiry_year": 2029,
        "cvv": "123"
    }
    
    response = requests.post(
        f"{BASE_URL}/users/payment-methods",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=payment_data
    )
    print(f"Add Payment Method: {response.status_code} - {response.json()}")

def run_tests():
    """Run all tests"""
    print("=== Testing Feature 1: Account Management ===\n")
    
    # Wait for service to be available
    if not wait_for_service():
        print("Service not available after maximum attempts")
        return
    
    # Continue with tests
    test_health()
    
    # Test registration
    token = test_user_registration()
    
    # Test login
    if not token:
        token = test_user_login()
    
    # Test profile operations
    test_get_profile(token)
    test_update_profile(token)
    test_add_payment_method(token)
    
    print("\n=== Tests Complete ===")

if __name__ == "__main__":
    run_tests()