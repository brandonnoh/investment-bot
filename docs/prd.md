# PRD — Next.js + shadcn/ui 프론트엔드 마이그레이션

## 개요
- 목표: 현재 Alpine.js + 바닐라 CSS 대시보드를 Next.js + shadcn/ui로 교체, Flask API는 그대로 유지
- 범위: `web/` 디렉토리 프론트엔드 전체 교체. `web/api.py`, `web/server.py` API 레이어는 변경 없음

## 기술 스택
- **Next.js 15** (App Router, TypeScript, `output: 'export'` 정적 빌드)
- **shadcn/ui** (Card, Table, Badge, Tabs, Button, Progress)
- **Tailwind CSS v4**
- **Recharts** (Chart.js 대체, shadcn 친화적)
- **SWR** (데이터 페칭 + 폴링)
- **빌드 결과물**: Flask가 `web/out/` 정적 파일 서빙

---

## Phase 1 — 기반 구축

- [ ] task-001 Next.js 프로젝트 초기화 + shadcn/ui 설치
- [ ] task-002 API 타입 정의 + 데이터 훅 (SWR)
- [ ] task-003 레이아웃: Header + 탭 네비게이션 + 글로벌 상태

## Phase 2 — 탭 구현

- [ ] task-004 개요 탭 (StatsStrip + HoldingsTable + 사이드바)
- [ ] task-005 포트폴리오 탭 (손익 차트 + 섹터 차트)
- [ ] task-006 AI 분석 탭 (Marcus 결과 + 이력 사이드패널)
- [ ] task-007 발굴 탭 (Opportunities 테이블 + 퀀트 스코어)
- [ ] task-008 알림 탭 + 시스템 탭 + 서비스 맵 탭

## Phase 3 — 통합

- [ ] task-009 Flask 서버 정적 빌드 서빙 + Docker 업데이트
