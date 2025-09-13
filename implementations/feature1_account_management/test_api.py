import requests
import json

BASE_URL = "http://localhost:5001"

def test_health():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health Check: {response.status_code} - {response.json()}")

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
    
    # Test health
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