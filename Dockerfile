FROM python:3.12

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src
COPY service_account.json ./service_account.json

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]
