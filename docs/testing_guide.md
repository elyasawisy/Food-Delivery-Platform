Testing Guide

This guide helps you quickly test API endpoints, uploads, and real-time features in this project.

1. Prerequisites

Make sure you have:

Python 3.10+ installed

All requirements installed for the feature you want to test:

pip install -r implementations/featureX/requirements.txt


Docker & Docker Compose (if using Docker setup)

Optional: .env file configured for secrets (if required by a feature)

2. Running the APIs
Option A: Local Python Server

For any feature, navigate to its folder and run the server. Example:

cd implementations/feature1_account_management
python main.py   # or the entrypoint for the feature


Server runs on http://localhost:8000 by default.

Option B: Using Docker
docker-compose up --build


This will start all services (API, DB, Redis, etc.) as configured.

3. Testing Features
Feature 1 – Account Management

Test script: implementations/feature1_account_management/test_api.py

Manual browser testing: implementations/feature1_account_management/test.html

Run the script:

python test_api.py

Feature 2 – Order Tracking

Test script: implementations/feature2_order_tracking/test_api.py

Manual testing: test.html inside the same folder

Run the script:

python test_api.py

Feature 3 – Driver Location (WebSocket)

Test script: implementations/feature3_driver_location/test_websocket.py

This script simulates real-time updates for driver location.

Feature 5 – Support Chat

Test scripts:

test_chat.py – backend API testing

test_client.html – frontend browser testing

Run backend test:

python test_chat.py


Open test_client.html in a browser to simulate a client.

Feature 7 – Image Upload

Test script: implementations/feature7_image_upload/test_api.py

Run:

python test_api.py


Verify files are uploaded to the configured folder or endpoint.

4. Troubleshooting

Connection errors: Make sure the API server is running and ports match scripts.

File upload fails: Check file size, type, and server write permissions.

Docker issues: Use:

docker-compose logs


to inspect container logs.