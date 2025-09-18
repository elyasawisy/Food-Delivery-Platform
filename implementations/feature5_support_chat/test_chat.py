import requests
import json
import socketio
import time

BASE_URL = "http://localhost:5005"
SOCKET_URL = "http://localhost:5005"

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f" Health check failed: {e}")
        return False

def main():
    print("=== Testing Feature 5: Support Chat ===\n")
    
    if not test_health():
        print("Service not available. Please check database connection.")
        return

if __name__ == "__main__":
    main()
