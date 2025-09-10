FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY feature4_restaurant_notifications.py .

EXPOSE 5000

CMD ["python", "feature4_restaurant_notifications.py"]