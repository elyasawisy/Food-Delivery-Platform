FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY ./implementations/feature3_driver_location/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application file
COPY ./implementations/feature3_driver_location/feature3_driver_location.py /app/

EXPOSE 5003

ENV FLASK_APP=feature3_driver_location.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5003
ENV PYTHONUNBUFFERED=1

CMD ["python", "feature3_driver_location.py"]