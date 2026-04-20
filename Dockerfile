FROM python:3.12-slim
WORKDIR /app

# Node.js + claude CLI 설치 (Marcus AI 분석용)
RUN apt-get update && apt-get install -y nodejs npm --no-install-recommends \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8421
CMD ["python3", "web/server.py"]
