# task-009: Flask 정적 빌드 서빙 + Docker 통합

## 배경
Next.js `output: 'export'`로 빌드하면 `web-next/out/` 에 정적 파일 생성됨. Flask 서버가 이를 서빙하도록 변경.

## 현재 코드 구조
- `web/server.py` 줄 1-264: ThreadingHTTPServer, 정적 파일 서빙 (`web/` 디렉토리)
- `Dockerfile`: `COPY . .` → `CMD ["python3", "web/server.py"]`

## 변경 방향

### web/server.py 수정
현재 줄 23-30에서 `WEB_DIR` 를 `web-next/out/`으로 변경:

현재:
```python
WEB_DIR = Path(__file__).parent  # web/
```

변경 후:
```python
_NEXT_OUT = Path(__file__).parent.parent / "web-next" / "out"
_LEGACY_DIR = Path(__file__).parent
WEB_DIR = _NEXT_OUT if _NEXT_OUT.exists() else _LEGACY_DIR
```

이렇게 하면 `web-next/out/`이 있으면 Next.js 빌드를 서빙, 없으면 기존 HTML 폴백.

### 정적 파일 라우팅 수정
Next.js 정적 export는 `out/index.html`, `out/404.html` 구조.
`do_GET`에서 `/` 요청 시 `out/index.html` 서빙, `/api/*`는 기존대로 처리.

현재 `do_GET` 줄 113 근처:
```python
if path.startswith("/api/") or path == "/api/events":
    # API 처리 (변경 없음)
else:
    # 정적 파일 서빙
    serve_static(path, WEB_DIR)
```

`serve_static` 함수에서 파일 없으면 `out/index.html` 폴백 (SPA 라우팅):
```python
def serve_static(path: str, web_dir: Path) -> None:
    file_path = web_dir / path.lstrip("/")
    if not file_path.exists():
        file_path = web_dir / "index.html"  # SPA fallback
    # 서빙 로직
```

### Dockerfile 수정
현재:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8421
CMD ["python3", "web/server.py"]
```

변경 후 (멀티 스테이지):
```dockerfile
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
```

### .dockerignore 추가/확인
```
web-next/node_modules
web-next/.next
web-next/out
```

## 검증 명령
```bash
docker compose build
docker compose up -d
curl -s -o /dev/null -w "%{http_code}" http://localhost:8421      # → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8421/api/data  # → 200
```
