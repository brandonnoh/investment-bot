FROM python:3.12-slim
WORKDIR /app

# Node.js + claude CLI + cron 설치 (Marcus AI 분석 + 스케줄러)
RUN apt-get update && apt-get install -y nodejs npm cron --no-install-recommends \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# KST 타임존 설정
RUN ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime \
    && echo "Asia/Seoul" > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# crontab 설치 (0644 필수, 0640이면 cron 데몬이 무시함)
COPY crontab.docker /etc/cron.d/investment-bot
RUN chmod 0644 /etc/cron.d/investment-bot

# 엔트리포인트 설치
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8421
CMD ["/entrypoint.sh"]
