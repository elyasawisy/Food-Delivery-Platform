FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./implementations/feature5_support_chat/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./implementations/feature5_support_chat/feature5_support_chat.py /app/

EXPOSE 5005

ENV FLASK_APP=feature5_support_chat.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5005
ENV PYTHONUNBUFFERED=1

CMD ["python", "feature5_support_chat.py"]