FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY feature3_driver_location.py .

EXPOSE 5000

ENV FLASK_APP=feature3_driver_location.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

CMD ["python", "feature3_driver_location.py"]