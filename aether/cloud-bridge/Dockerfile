FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Default connection string for SITL (assuming --network host or same docker network)
ENV MAVLINK_CONNECTION="udp:0.0.0.0:14550"

CMD ["python", "-m", "src.main"]
