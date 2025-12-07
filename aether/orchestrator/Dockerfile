FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Certificates are mounted at runtime

CMD ["python", "-u", "src/main.py"]
