# Stage 1: Next.js 빌드
FROM node:20-alpine AS frontend-builder
WORKDIR /app/web-next
COPY web-next/package*.json ./
RUN npm ci
COPY web-next/ .
RUN npm run build

# Stage 2: Python 서버
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend-builder /app/web-next/out ./web-next/out
EXPOSE 8421
CMD ["python3", "web/server.py"]
