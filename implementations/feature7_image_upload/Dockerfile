FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    python3-tk \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./implementations/feature7_image_upload/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /tmp/uploads /tmp/processed

COPY ./implementations/feature7_image_upload/feature7_image_upload.py .
COPY ./implementations/feature7_image_upload/celery.py .
COPY ./implementations/feature7_image_upload/celeryconfig.py .

EXPOSE 5000

# Change CMD for worker
CMD ["celery", "-A", "celery", "worker", "--loglevel=info"]