FROM python:3.11-slim

WORKDIR /app

# Install psycopg2 dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY ./implementations/feature2_order_tracking/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./implementations/feature2_order_tracking/feature2_order_tracking.py /app/

EXPOSE 5000

# Run with Gunicorn instead of Flask dev server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "feature2_order_tracking:app"]
