FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir "torch>=2.6,<3" --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV XOW_DATA=/data
EXPOSE 8787
CMD ["python", "-u", "server.py", "--host", "0.0.0.0", "--port", "8787"]
