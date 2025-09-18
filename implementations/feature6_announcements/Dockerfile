FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including PostgreSQL
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./implementations/feature6_announcements/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./implementations/feature6_announcements/feature6_announcements.py /app/

EXPOSE 5000

CMD ["python", "feature6_announcements.py"]