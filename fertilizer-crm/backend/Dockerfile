FROM python:3.11-slim

WORKDIR /app

# ไม่ต้องติดตั้ง libpq-dev/gcc — ใช้ psycopg2-binary และทุก dependency มี prebuilt wheel
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
