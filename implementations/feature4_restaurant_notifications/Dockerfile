FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY ./implementations/feature4_restaurant_notifications/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application file
COPY ./implementations/feature4_restaurant_notifications/feature4_restaurant_notifications.py /app/

EXPOSE 5004

ENV FLASK_APP=feature4_restaurant_notifications.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5004

CMD ["python", "feature4_restaurant_notifications.py"]