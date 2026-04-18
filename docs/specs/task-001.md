# task-001: Next.js 프로젝트 초기화 + shadcn/ui 설치

## 배경
현재 프론트엔드는 `web/index.html` (1262줄) + Alpine.js + 바닐라 CSS. shadcn/ui 기반으로 교체하기 위해 Next.js 프로젝트를 새로 스캐폴딩한다.

## 디렉토리 위치
프로젝트 루트(`/Users/jarvis/Projects/investment-bot/`) 아래 `web-next/` 생성.

## 구현 방향

### Step 1: Next.js 초기화
```bash
cd /Users/jarvis/Projects/investment-bot
npx create-next-app@latest web-next \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --import-alias "@/*"
```
→ `web-next/` 생성됨

실제로는 src/ 디렉토리 구조로 가도 됨. `--src-dir` 옵션 추가 가능.

### Step 2: 의존성 추가
```bash
cd web-next
npm install recharts swr zustand react-markdown
npm install -D @types/node
```

### Step 3: shadcn/ui 초기화
```bash
cd web-next
npx shadcn@latest init
```
프롬프트:
- Style: Default
- Base color: Neutral (나중에 커스텀)
- CSS variables: Yes

### Step 4: 필요한 shadcn 컴포넌트 설치
```bash
npx shadcn@latest add card table badge button tabs progress
```

### Step 5: next.config.ts 설정
```typescript
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'export',         // 정적 빌드 → out/ 디렉토리
  trailingSlash: true,
  images: { unoptimized: true },
}

export default nextConfig
```

### Step 6: 테마 색상 설정 (globals.css)
현재 CSS 변수를 Tailwind + shadcn 테마로 변환:

```css
/* web-next/src/app/globals.css */
@import "tailwindcss";

:root {
  --background: #0c0b0a;
  --foreground: #e2d9d0;
  --muted: #9a8e84;
  --muted-foreground: #5a504a;
  --card: #131210;
  --card-foreground: #e2d9d0;
  --border: #2a2420;
  --gold: #c9a93a;
  --gold-bg: rgba(201,169,58,0.08);
  --green: #4dca7e;
  --red: #e05656;
  --amber: #e09b3d;
}
```

tailwind.config.ts에서 커스텀 색상 extend:
```typescript
theme: {
  extend: {
    colors: {
      gold: '#c9a93a',
      'mc-bg': '#0c0b0a',
      'mc-card': '#131210',
      'mc-border': '#2a2420',
      'mc-green': '#4dca7e',
      'mc-red': '#e05656',
    },
    fontFamily: {
      sans: ['Space Grotesk', 'system-ui', 'sans-serif'],
      mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
    },
  },
}
```

### Step 7: 폰트 설정 (layout.tsx)
```typescript
import { Space_Grotesk, JetBrains_Mono } from 'next/font/google'

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space-grotesk',
})
const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
})
```

### Step 8: 환경변수
`web-next/.env.local`:
```
NEXT_PUBLIC_API_BASE=http://localhost:8421
```

## 검증 명령
```bash
cd web-next && npm run build
# → out/ 디렉토리 생성 확인
ls out/
```

## 주의사항
- `output: 'export'`이면 SSE(EventSource) 클라이언트 코드는 동작함 (브라우저에서 Flask로 직접 연결)
- API 호출은 모두 `NEXT_PUBLIC_API_BASE` 기준으로 절대 경로 사용
- `git` 커밋은 메인 세션이 함 — 에이전트는 커밋하지 않음
