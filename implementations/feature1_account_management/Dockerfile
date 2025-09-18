FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY ./implementations/feature1_account_management/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./implementations/feature1_account_management/feature1_account_management.py /app/

# Set environment variables
ENV FLASK_APP=feature1_account_management.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5001
ENV PYTHONUNBUFFERED=1

EXPOSE 5001

CMD ["python", "feature1_account_management.py"]