# Food Delivery Platform Setup Instructions

## Prerequisites
- Install Docker & Docker Compose
- Optional: Python 3.10+ for local testing
- Optional: PostgreSQL & Redis if running outside Docker

---

## 1. Clone the Repository
```bash
git https://github.com/elyasawisy/Food-Delivery-Platform.git
cd Food-Delivery-Platform




Create a .env file in the root folder
Build and Run with Docker
Access Services


Optional: Run Locally without Docker
# Create virtual environment
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r feature7_image_upload/requirements.txt

# Start service
python feature7_image_upload/feature7_image_upload.py

# Start Celery worker
celery -A feature7_image_upload.feature7_image_upload.celery worker --loglevel=info

