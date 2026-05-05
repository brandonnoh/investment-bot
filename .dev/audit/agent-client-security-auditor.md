# 클라이언트/프론트엔드 보안 감사 보고서

**프로젝트:** `/Users/jarvis/Projects/investment-bot/web-next`
**감사 기준:** OWASP A03 (Injection), A05 (Security Misconfiguration)
**감사 일자:** 2026-05-02
**기술 스택:** Next.js 16.2.4 · React 19 · TypeScript · Zustand · SWR · react-markdown 10

---

## 발견된 취약점 목록

### SEC-F-001
**파일:라인** `src/app/api/[...path]/route.ts:11`

**설명** SSE 응답 헤더에 `Access-Control-Allow-Origin: *` 하드코딩. 내부 대시보드임에도 모든 origin의 EventSource 연결을 허용한다.

**심각도** 중간 (Medium)

**OWASP** A05 Security Misconfiguration

**증거**
```typescript
const SSE_HEADERS = {
  'Content-Type': 'text/event-stream',
  'Cache-Control': 'no-cache',
  Connection: 'keep-alive',
  'Access-Control-Allow-Origin': '*',   // ← 와일드카드
}
```
이 헤더는 `/api/events` 및 `/api/investment-advice-stream` 두 SSE 경로에 모두 적용된다 (26라인, 49라인).

**영향** 공격자가 다른 도메인에서 `new EventSource('http://target/api/events')`를 호출해 실시간 포트폴리오 이벤트 스트림을 탈취할 수 있다. 특히 피싱 페이지에서 피해자의 브라우저를 경유하는 크로스-사이트 정보 유출 경로가 된다.

---

### SEC-F-002
**파일:라인** `src/app/api/[...path]/route.ts:14-16`

**설명** 프록시가 `path` 배열을 아무런 검증 없이 Flask URL로 직접 결합한다. path traversal 시퀀스(`../`, `%2e%2e`) 또는 내부망 경로를 삽입해 Flask가 노출하는 다른 내부 엔드포인트를 우회 접근(SSRF 유사)할 수 있다.

**심각도** 높음 (High)

**OWASP** A03 Injection (경로 인젝션) / A05 Misconfiguration

**증거**
```typescript
async function proxy(req: NextRequest, path: string[]) {
  const pathStr = path.join('/')
  const url = `${API_BASE}/api/${pathStr}${req.nextUrl.search}`
  // 화이트리스트 검사, 정규화, 인코딩 처리 전무
```
예: `GET /api/..%2F..%2Finternal/admin` → Flask의 숨겨진 내부 경로로 전달될 수 있다.

**영향** Flask API가 같은 프로세스 내에서 노출하는 `/api/run-pipeline`, `/api/run-marcus` 등 위험한 POST 엔드포인트를 외부 요청자가 GET 프록시를 통해 경로를 조작하여 도달할 가능성. 또한 `req.nextUrl.search` (쿼리스트링) 역시 그대로 전달되므로 쿼리파라미터 인젝션도 가능하다.

---

### SEC-F-003
**파일:라인** `src/app/api/[...path]/route.ts:5`

**설명** `PYTHON_API_URL` 환경변수가 설정되지 않으면 `http://localhost:8421`로 폴백. 이 변수는 `NEXT_PUBLIC_` 접두사가 없어 서버 사이드 전용이므로 노출 자체는 아니지만, 환경변수 미설정 시 컨테이너 네트워크 내부에서 호스트 기반 SSRF 가능성이 상존한다.

**심각도** 낮음 (Low) — 폴백 자체는 의도된 설계이나 문서화 필요

**OWASP** A05 Security Misconfiguration

**증거**
```typescript
const API_BASE = process.env.PYTHON_API_URL ?? 'http://localhost:8421'
```

**영향** Docker 환경에서 `PYTHON_API_URL`이 주입되지 않으면 localhost:8421을 가리키며, 동일 컨테이너 내 다른 서비스가 그 포트를 점유하는 경우 의도치 않은 대상으로 프록시된다.

---

### SEC-F-004
**파일:라인** `src/components/tabs/AdvisorTab.tsx:47`

**설명** 개인 투자 민감 정보(`capital`, `riskLevel`, `minusLoan`, `creditLoan`, `monthlySavings`, `portfolioMode`)가 평문으로 `localStorage`에 저장된다.

**심각도** 중간 (Medium)

**OWASP** A05 Security Misconfiguration

**증거**
```typescript
const LS_KEY = 'mc-advisor-settings'

function saveSettings(...) {
  localStorage.setItem(LS_KEY, JSON.stringify({
    capital, riskLevel, minusLoan, creditLoan, monthlySavings, portfolioMode
  }))
}
```
저장되는 항목 예시: `capital: 150000000`, `minusLoan: { amount: 50000000, rate: 4.0 }`, `creditLoan: { amount: 30000000, rate: 6.5, gracePeriod: 3, repayPeriod: 36 }`.

**영향** 같은 브라우저에서 실행되는 다른 JavaScript (서드파티 스크립트, 브라우저 익스텐션, XSS)가 `localStorage.getItem('mc-advisor-settings')`로 자산 규모, 레버리지 규모, 대출 금리 정보를 평문으로 읽을 수 있다. sessionStorage도 동일한 리스크를 가지나 브라우저 종료 시 삭제되어 더 낫다.

---

### SEC-F-005
**파일:라인** `src/hooks/useSSE.ts:14`

**설명** `EventSource` 연결 시 수신 메시지에 대해 origin 검증이 없다. `e.origin` 체크 누락.

**심각도** 낮음 (Low) — 현재 구조상 직접 익스플로잇은 어려우나 방어적 코딩 부재

**OWASP** A05 Security Misconfiguration

**증거**
```typescript
es.onmessage = (e) => {
  const msg = e.data?.trim()
  if (msg === 'ping' || msg === 'connected') return
  void mutate('intel-data')
  void mutate('process-status')
  // e.origin 검증 없음
}
```

**영향** 로컬 개발 환경에서 잘못된 SSE 서버가 같은 포트를 점유하거나 중간자(MITM) 상황에서 조작된 SSE 이벤트로 SWR 캐시를 강제 무효화해 불필요한 API 요청을 유발할 수 있다.

---

### SEC-F-006
**파일:라인** `src/lib/api.ts:38`

**설명** `fetchLogs` 함수가 `name` 파라미터를 인코딩 없이 쿼리스트링에 직접 삽입한다.

**심각도** 낮음 (Low)

**OWASP** A03 Injection

**증거**
```typescript
export async function fetchLogs(name: string, lines = 50): Promise<LogResponse> {
  return apiFetch<LogResponse>(`/api/logs?name=${name}&lines=${lines}`)
  //                                         ↑ encodeURIComponent 없음
}
```
현재 호출처(`useMarcusLog.ts:10`)는 하드코딩된 `'marcus'` 문자열만 전달하므로 즉각적 위험은 낮다. 그러나 향후 `name`이 사용자 입력에 연결되면 쿼리파라미터 인젝션(`?name=marcus&admin=true`) 또는 Flask 측 로그 파일 경로 조작이 가능해진다.

**영향** Flask의 `name` 파라미터 허용 목록 검증이 취약할 경우 임의 로그 파일 접근 가능.

---

### SEC-F-007
**파일:라인** `next.config.ts` (전체)

**설명** `Content-Security-Policy(CSP)` 헤더가 전혀 설정되어 있지 않다.

**심각도** 높음 (High)

**OWASP** A05 Security Misconfiguration

**증거**
```typescript
const nextConfig: NextConfig = {
  output: 'standalone',
  images: { unoptimized: true },
  async headers() {
    return [
      { source: '/', headers: [{ key: 'Cache-Control', value: 'no-cache...' }] },
      { source: '/_next/static/:path*', headers: [{ key: 'Cache-Control', ... }] },
    ]
  },
}
// Content-Security-Policy, X-Frame-Options, X-Content-Type-Options,
// Referrer-Policy, Permissions-Policy 모두 누락
```

**영향** CSP 부재 시 XSS 공격의 피해 범위가 극대화된다. 인라인 스크립트 실행, 외부 스크립트 로드, 데이터 외부 전송 모두 브라우저가 차단하지 않는다. `X-Frame-Options` 누락으로 Clickjacking도 가능하다. `X-Content-Type-Options: nosniff` 미설정으로 MIME 스니핑 공격에도 취약하다.

---

### SEC-F-008
**파일:라인** `src/components/tabs/MarcusTab.tsx:136`, `src/components/advisor/AIAdvisorPanel.tsx:187`, `src/components/tabs/SavedStrategiesTab.tsx:120`

**설명** `react-markdown`이 서버 AI(Claude) 응답을 그대로 렌더링한다. `rehype-raw` 플러그인은 사용하지 않아 현재 HTML 태그는 이스케이프되지만, AI 모델이 마크다운 코드 블록 밖에 `<script>` 또는 `javascript:` URI를 생성하는 경우를 대비한 추가 방어가 없다.

**심각도** 낮음 (Low) — 현재 설정상 직접 HTML 렌더링은 차단됨, 그러나 잠재적 위험

**OWASP** A03 Injection (XSS)

**증거**
```typescript
// MarcusTab.tsx:136
<ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
  {content}   // ← Flask가 반환한 AI 생성 마크다운 원문
</ReactMarkdown>

// AIAdvisorPanel.tsx:187
<ReactMarkdown remarkPlugins={[remarkGfm]}>
  {displayText}  // ← AI 스트리밍 응답 (components 커스터마이징 없음)
</ReactMarkdown>
```
`AIAdvisorPanel`과 `SavedStrategiesTab`의 `ReactMarkdown`은 `MD_COMPONENTS` 커스터마이징조차 없어 react-markdown 기본 렌더러가 링크(`<a>`)를 그대로 생성하며 `rel` 속성도 주입되지 않는다.

**영향** `rehype-raw` 없이는 직접 XSS는 불가능하나, AI 프롬프트 인젝션으로 `[클릭](javascript:alert(1))` 형태의 링크가 생성되면 `<a href="javascript:...">` 형태로 렌더링될 수 있다. react-markdown v10은 기본적으로 `javascript:` URI를 차단하지 않는다.

---

### SEC-F-009
**파일:라인** `src/components/discovery/DrawerSections.tsx:339-341`

**설명** 뉴스 아이템의 `item.url`이 Flask API에서 수신한 외부 URL 그대로 `<a href>` 에 삽입된다. URL 스킴 검증이 없다.

**심각도** 중간 (Medium)

**OWASP** A03 Injection (XSS via javascript: URI)

**증거**
```typescript
function NewsItem({ item }: { item: CompanyNewsItem }) {
  const Wrapper = item.url ? 'a' : 'div'
  const linkProps = item.url
    ? { href: item.url, target: '_blank' as const, rel: 'noopener noreferrer' }
    : {}
```
`item.url`이 `javascript:void(0)` 또는 `javascript:alert(document.cookie)` 값을 가지면 그대로 렌더링된다. `rel="noopener noreferrer"`는 있으나 href 스킴 검증은 없다.

**영향** Flask API 또는 뉴스 수집 파이프라인이 오염된 경우(공급망 공격, DART/Naver API 응답 조작), 사용자가 뉴스 링크를 클릭할 때 JavaScript가 실행된다.

---

### SEC-F-010
**파일:라인** `src/components/discovery/DrawerSections.tsx:168-173`

**설명** `profile.website` 역시 Flask API에서 받은 URL을 `<a href>` 에 직접 삽입하며 스킴 검증이 없다.

**심각도** 중간 (Medium)

**OWASP** A03 Injection (XSS via javascript: URI)

**증거**
```typescript
{profile.website && (
  <a
    href={profile.website}   // ← 스킴 검증 없음
    target="_blank"
    rel="noopener noreferrer"
    ...
  >
    <ExternalLink size={9} /> 웹사이트
  </a>
)}
```

**영향** SEC-F-009와 동일한 공격 경로. 기업 프로필 데이터(`company_profiles` DB 테이블)가 조작되면 웹사이트 링크 클릭 시 JavaScript 실행.

---

### SEC-F-011
**파일:라인** `src/store/useMCStore.ts:31`

**설명** URL 쿼리파라미터 `?tab=` 값을 `VALID_TABS` 배열로 화이트리스트 검사하고 있으나, `localStorage.getItem('mc-active-tab')` 폴백은 검증이 없다.

**심각도** 낮음 (Low)

**OWASP** A03 Injection (DOM-based)

**증거**
```typescript
function getInitialTab(): TabId {
  try {
    const urlTab = new URLSearchParams(window.location.search).get('tab') as TabId | null
    if (urlTab && VALID_TABS.includes(urlTab)) return urlTab  // ← URL은 검증
    return (localStorage.getItem('mc-active-tab') as TabId) ?? 'overview'  // ← localStorage는 검증 없이 TypeScript 타입 단언만
  }
}
```
`localStorage`의 `mc-active-tab` 값이 유효하지 않은 TabId일 경우 렌더링 로직에서 어떤 탭도 매칭되지 않아 빈 화면이 표시된다. 현재는 기능 오류 수준이나 향후 탭 렌더링에 동적 로직이 추가되면 인젝션 경로가 될 수 있다.

**영향** 현재는 빈 화면(빈 렌더링) 수준. 향후 코드 변경 시 위험도 상승 가능.

---

## 요약 테이블

| ID | 파일 | 심각도 | OWASP | 항목 |
|----|------|--------|-------|------|
| SEC-F-001 | route.ts:11 | 중간 | A05 | SSE CORS 와일드카드 |
| SEC-F-002 | route.ts:14-16 | **높음** | A03/A05 | 프록시 경로 검증 없음 (경로 인젝션) |
| SEC-F-003 | route.ts:5 | 낮음 | A05 | PYTHON_API_URL 폴백 localhost |
| SEC-F-004 | AdvisorTab.tsx:47 | 중간 | A05 | 투자 민감정보 localStorage 평문 저장 |
| SEC-F-005 | useSSE.ts:14 | 낮음 | A05 | SSE origin 검증 없음 |
| SEC-F-006 | api.ts:38 | 낮음 | A03 | 로그 name 파라미터 미인코딩 |
| SEC-F-007 | next.config.ts | **높음** | A05 | CSP/보안 헤더 전무 |
| SEC-F-008 | MarcusTab.tsx:136 등 | 낮음 | A03 | AI 응답 react-markdown 렌더링 (javascript: URI 미차단) |
| SEC-F-009 | DrawerSections.tsx:339 | 중간 | A03 | 뉴스 URL 스킴 검증 없음 |
| SEC-F-010 | DrawerSections.tsx:168 | 중간 | A03 | 기업 website URL 스킴 검증 없음 |
| SEC-F-011 | useMCStore.ts:31 | 낮음 | A03 | localStorage 탭값 미검증 |

---

## 우선순위 권고

1. **즉시 (높음):** SEC-F-007 — `next.config.ts`에 CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` 헤더 추가
2. **즉시 (높음):** SEC-F-002 — `route.ts` 프록시에 허용 경로 화이트리스트 또는 최소한 `../` 패턴 차단
3. **단기 (중간):** SEC-F-001 — SSE CORS를 `Access-Control-Allow-Origin: http://100.90.201.87:3000` 등 명시적 origin으로 제한
4. **단기 (중간):** SEC-F-009, SEC-F-010 — URL href 삽입 전 `url.startsWith('https://') || url.startsWith('http://')` 스킴 검증 추가
5. **중기 (중간):** SEC-F-004 — `mc-advisor-settings`에서 대출 금액/금리 등 금융 민감값 제거 또는 sessionStorage로 이전
