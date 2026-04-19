/**
 * 미션컨트롤 메인 로직
 * SSE 구독, 데이터 렌더링, Chart.js 초기화
 */

// Chart.js 전역 다크 테마 설정
Chart.defaults.color = '#9a8e84';
Chart.defaults.borderColor = '#2a2420';
Chart.defaults.plugins.legend.labels.color = '#9a8e84';
Chart.defaults.plugins.legend.labels.font = { family: "'Space Grotesk', system-ui, sans-serif", size: 11 };

// 다크 tooltip 공통 옵션 (각 차트에 직접 주입)
const TOOLTIP_DARK = {
  backgroundColor: '#1a1714',
  borderColor: '#2a2420',
  borderWidth: 1,
  titleColor: '#e2d9d0',
  bodyColor: '#c8bfb5',
  padding: 10,
  cornerRadius: 4,
  displayColors: true,
  boxPadding: 4,
  titleFont: { family: "'Space Grotesk', sans-serif", size: 12, weight: '600' },
  bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
};

// 전역 Alpine.js 스토어
document.addEventListener('alpine:init', () => {
  Alpine.store('mc', {
    // 현재 탭
    tab: 'overview',

    // 데이터
    data: {},
    lastUpdated: null,
    sseStatus: 'disconnected', // connected | disconnected

    // 프로세스 상태
    pipelineRunning: false,
    marcusRunning: false,

    // 로딩
    loading: false,

    // 파싱된 뷰 데이터
    prices: [],
    macro: [],
    portfolio: {},
    alerts: [],
    regime: {},
    priceAnalysis: {},
    engineStatus: {},
    opportunities: [],
    screener: {},
    news: [],
    fundamentals: [],
    supplyData: {},
    holdingsProposal: {},
    performance: {},
    simulation: {},
    marcusMd: '',
    cioBriefingMd: '',
    dailyReportMd: '',

    // AI 분석 이력
    analysisHistory: [],
    selectedAnalysis: null,

    // AI 분석 진행 상태
    marcusLog: [],
    aiSteps: [],       // 완료된 step 번호 배열
    aiCurrentStep: 0,  // 현재 실행 중인 step
    _logPollTimer: null,
    aiStepDefs: [
      'JSON 데이터 로드', '실시간 시세 수집', '페르소나 로드',
      '프롬프트 조립', 'Claude 실행', '결과 저장',
      '검증', 'Discord 알림', '완료'
    ],

    // 차트 인스턴스
    _charts: {},

    // 초기화
    async init() {
      await this.fetchData();
      this.initSSE();
      this.pollStatus();
      this.fetchAnalysisHistory();
    },

    // SSE 구독
    initSSE() {
      const es = new EventSource('/api/events');
      es.onopen = () => {
        this.sseStatus = 'connected';
      };
      es.onmessage = (e) => {
        if (e.data === 'update') {
          this.fetchData();
        }
      };
      es.onerror = () => {
        this.sseStatus = 'disconnected';
        // 5초 후 재연결
        setTimeout(() => this.initSSE(), 5000);
        es.close();
      };
    },

    // 데이터 로드
    async fetchData() {
      try {
        const res = await fetch('/api/data');
        if (!res.ok) return;
        const raw = await res.json();
        this.data = raw;
        this.parseData(raw);
        this.lastUpdated = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
        Alpine.nextTick(() => this.renderCharts(raw));
      } catch (e) {
        console.error('[mc] 데이터 로드 실패:', e);
      }
    },

    // 프로세스 상태 폴링 (15초 간격)
    async pollStatus() {
      const check = async () => {
        try {
          const res = await fetch('/api/status');
          if (res.ok) {
            const s = await res.json();
            this.pipelineRunning = s.pipeline?.running ?? false;
            this.marcusRunning = s.marcus?.running ?? false;
          }
        } catch (_) {}
      };
      await check();
      setInterval(check, 15000);
    },

    // 데이터 파싱
    parseData(raw) {
      this.prices = raw.prices?.prices ?? [];
      this.macro = raw.macro?.indicators ?? [];
      this.portfolio = raw.portfolio_summary ?? {};
      this.alerts = raw.alerts?.alerts ?? [];
      this.regime = raw.regime ?? {};
      this.priceAnalysis = raw.price_analysis?.analysis ?? {};
      this.engineStatus = raw.engine_status ?? {};
      this.opportunities = raw.opportunities?.opportunities ?? [];
      this.screener = raw.screener_results ?? {};
      this.news = (raw.news?.news ?? []).slice(0, 10);
      this.fundamentals = raw.fundamentals?.fundamentals ?? [];
      this.supplyData = raw.supply_data ?? {};
      this.holdingsProposal = raw.holdings_proposal ?? {};
      this.performance = raw.performance_report ?? {};
      this.simulation = raw.simulation_report ?? {};
      this.marcusMd = raw.marcus_analysis ?? '';
      this.cioBriefingMd = raw.cio_briefing ?? '';
      this.dailyReportMd = raw.daily_report ?? '';
    },

    // 마크다운 렌더링
    renderMarkdown(text) {
      if (!text || typeof marked === 'undefined') return text || '';
      return marked.parse(text);
    },

    // Chart.js 차트 렌더링
    renderCharts(raw) {
      this.renderPortfolioChart(raw);
      this.renderSectorChart(raw);
      this.renderOpportunityChart(raw);
    },

    // 포트폴리오 히스토리 라인 차트
    renderPortfolioChart(raw) {
      const canvas = document.getElementById('chart-portfolio');
      if (!canvas) return;

      const history = raw.portfolio_summary?.history ?? [];
      if (history.length === 0) {
        // 현재 값만으로 더미 포인트 생성
        const total = raw.portfolio_summary?.total ?? {};
        if (!total.pnl_pct) return;
      }

      const labels = history.map(h => {
        const d = new Date(h.date ?? h.timestamp ?? '');
        return isNaN(d) ? h.date : `${d.getMonth()+1}/${d.getDate()}`;
      });
      const pnlData = history.map(h => +(h.pnl_pct ?? h.total_pnl_pct ?? 0).toFixed(2));

      if (this._charts['portfolio']) {
        this._charts['portfolio'].destroy();
      }

      const ctx = canvas.getContext('2d');
      this._charts['portfolio'] = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: '수익률 (%)',
            data: pnlData,
            borderColor: '#c9a93a',
            backgroundColor: 'rgba(201,169,58,0.08)',
            borderWidth: 2,
            pointRadius: 3,
            fill: true,
            tension: 0.3,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              ...TOOLTIP_DARK,
              callbacks: {
                label: (ctx) => ` ${ctx.parsed.y}%`
              }
            }
          },
          scales: {
            x: { ticks: { color: '#5a504a', font: { family: "'JetBrains Mono', monospace", size: 10 } }, grid: { color: '#2a2420' } },
            y: { ticks: { color: '#5a504a', font: { family: "'JetBrains Mono', monospace", size: 10 } }, grid: { color: '#2a2420' } }
          }
        }
      });
    },

    // 섹터 도넛 차트
    renderSectorChart(raw) {
      const canvas = document.getElementById('chart-sector');
      if (!canvas) return;

      const holdings = raw.portfolio_summary?.holdings ?? [];
      if (holdings.length === 0) return;

      // 섹터별 비중 집계
      const sectorMap = {};
      let totalVal = 0;
      for (const h of holdings) {
        const sec = h.sector || '기타';
        sectorMap[sec] = (sectorMap[sec] ?? 0) + (h.current_value_krw ?? 0);
        totalVal += (h.current_value_krw ?? 0);
      }

      const sectors = Object.keys(sectorMap);
      const values = sectors.map(s => sectorMap[s]);
      const COLORS = ['#c9a93a','#4dca7e','#e09b3d','#e05656','#4ec9b0','#9a8e84','#7b6d8d','#b58a5a'];

      if (this._charts['sector']) {
        this._charts['sector'].destroy();
      }

      const ctx = canvas.getContext('2d');
      this._charts['sector'] = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: sectors,
          datasets: [{
            data: values,
            backgroundColor: COLORS.slice(0, sectors.length),
            borderColor: '#0c0b0a',
            borderWidth: 2,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '65%',
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#9a8e84', font: { family: "'Space Grotesk', system-ui, sans-serif", size: 11 }, padding: 10, boxWidth: 12 }
            },
            tooltip: {
              ...TOOLTIP_DARK,
              callbacks: {
                label: (ctx) => {
                  const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                  const pct = total ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                  return ` ${ctx.label}: ${pct}%`;
                }
              }
            }
          }
        }
      });
    },

    // 발굴 기회 바 차트
    renderOpportunityChart(raw) {
      const canvas = document.getElementById('chart-opportunity');
      if (!canvas) return;

      const opps = raw.opportunities?.opportunities ?? [];
      if (opps.length === 0) return;

      const sorted = [...opps].sort((a, b) => (b.composite_score ?? 0) - (a.composite_score ?? 0)).slice(0, 8);
      const labels = sorted.map(o => o.name ?? o.ticker);
      const scores = sorted.map(o => +(o.composite_score * 100).toFixed(1));
      const colors = scores.map(s => s >= 80 ? '#4dca7e' : s >= 60 ? '#c9a93a' : '#e09b3d');

      if (this._charts['opportunity']) {
        this._charts['opportunity'].destroy();
      }

      const ctx = canvas.getContext('2d');
      this._charts['opportunity'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: '종합 점수',
            data: scores,
            backgroundColor: colors,
            borderRadius: 4,
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              ...TOOLTIP_DARK,
              callbacks: {
                label: (ctx) => ` 점수: ${ctx.parsed.x}/100`
              }
            }
          },
          scales: {
            x: {
              min: 0, max: 100,
              ticks: { color: '#5a504a', font: { family: "'JetBrains Mono', monospace", size: 10 } },
              grid: { color: '#2a2420' }
            },
            y: { ticks: { color: '#e2d9d0', font: { family: "'Space Grotesk', system-ui, sans-serif", size: 11 } }, grid: { display: false } }
          }
        }
      });
    },

    // 파이프라인 실행
    async runPipeline() {
      if (this.pipelineRunning) return;
      this.pipelineRunning = true;
      try {
        const res = await fetch('/api/run-pipeline', { method: 'POST' });
        const data = await res.json();
        if (!data.ok) {
          alert(data.error ?? '파이프라인 실행 실패');
          this.pipelineRunning = false;
        }
      } catch (e) {
        alert('서버 오류: ' + e.message);
        this.pipelineRunning = false;
      }
    },

    // AI 분석 이력 로드
    async fetchAnalysisHistory() {
      try {
        const res = await fetch('/api/analysis-history');
        if (res.ok) this.analysisHistory = await res.json();
      } catch (e) {
        console.error('[mc] 분석 이력 로드 실패:', e);
      }
    },

    // 특정 날짜 분석 상세 조회
    async selectAnalysis(date) {
      if (this.selectedAnalysis?.date === date) {
        this.selectedAnalysis = null;
        return;
      }
      try {
        const res = await fetch(`/api/analysis-history?date=${date}`);
        if (res.ok) this.selectedAnalysis = await res.json();
      } catch (e) {
        console.error('[mc] 분석 상세 로드 실패:', e);
      }
    },

    // AI 분석 실행
    async runMarcus() {
      if (this.marcusRunning) return;
      this.marcusRunning = true;
      this.marcusLog = [];
      this.aiSteps = [];
      this.aiCurrentStep = 0;
      try {
        const res = await fetch('/api/run-marcus', { method: 'POST' });
        const data = await res.json();
        if (!data.ok) {
          alert(data.error ?? 'AI 분석 실행 실패');
          this.marcusRunning = false;
        } else {
          this.startLogPoll();
        }
      } catch (e) {
        alert('서버 오류: ' + e.message);
        this.marcusRunning = false;
      }
    },

    // 로그 폴링 시작
    startLogPoll() {
      if (this._logPollTimer) clearInterval(this._logPollTimer);
      this._logPollTimer = setInterval(() => this.pollMarcusLog(), 2000);
    },

    // 로그 폴링 중단
    stopLogPoll() {
      if (this._logPollTimer) {
        clearInterval(this._logPollTimer);
        this._logPollTimer = null;
      }
    },

    // 로그 한 번 가져오기
    async pollMarcusLog() {
      try {
        const res = await fetch('/api/logs?name=marcus&lines=100');
        if (!res.ok) return;
        const data = await res.json();
        this.marcusLog = data.lines ?? [];

        // [N/9] 패턴 파싱 → 완료 step 추출
        const done = new Set();
        let current = 0;
        for (const line of this.marcusLog) {
          const m = line.match(/\[(\d+)\/9\]/);
          if (m) {
            const n = parseInt(m[1]);
            done.add(n);
            if (n > current) current = n;
          }
        }
        this.aiSteps = [...done];
        this.aiCurrentStep = current;

        // 프로세스 종료 감지 — 로그 완료 마커 우선
        const finished = this.marcusLog.some(l =>
          l.includes('실행기 종료') || l.includes('=== 마커스 분석 실행기 종료') || l.includes('[9/9]')
        );
        if (finished) {
          this.marcusRunning = false;
          this.aiCurrentStep = 9;
          this.aiSteps = [1,2,3,4,5,6,7,8,9];
          this.stopLogPoll();
          this.fetchAnalysisHistory();
          this.fetchData();
        }
      } catch (_) {}
    },

    // 숫자 포맷 헬퍼
    fmtPct(v, decimals = 2) {
      if (v == null || isNaN(v)) return '-';
      const n = +v;
      const s = (n >= 0 ? '+' : '') + n.toFixed(decimals) + '%';
      return s;
    },

    fmtKrw(v) {
      if (v == null || isNaN(v)) return '-';
      return (+v).toLocaleString('ko-KR') + '원';
    },

    fmtNum(v, decimals = 2) {
      if (v == null || isNaN(v)) return '-';
      return (+v).toFixed(decimals);
    },

    pctClass(v) {
      if (v == null || isNaN(v)) return 'muted';
      return +v >= 0 ? 'green' : 'red';
    },

    // 시장 국면 색상
    regimeColor(regime) {
      const map = {
        'BULL': 'green',
        'BEAR': 'red',
        'INFLATIONARY': 'yellow',
        'DEFLATIONARY': 'blue',
        'CRISIS': 'red',
        'NEUTRAL': 'muted',
      };
      return map[regime] ?? 'muted';
    },

    // Fear&Greed 색상
    fearGreedColor(score) {
      if (score == null) return 'muted';
      if (score <= 25) return 'red';
      if (score <= 45) return 'orange';
      if (score <= 55) return 'yellow';
      if (score <= 75) return 'green';
      return 'green';
    },

    // RSI 신호 색상
    rsiColor(signal) {
      if (!signal) return 'muted';
      if (signal === 'oversold') return 'red';
      if (signal === 'overbought') return 'yellow';
      return 'muted';
    },

    // MA 신호 색상
    maColor(signal) {
      if (!signal) return 'muted';
      if (signal === 'golden_cross') return 'green';
      if (signal === 'dead_cross') return 'red';
      return 'muted';
    },

    // 뉴스 감성 배지
    sentimentBadge(v) {
      if (v > 0.3) return { cls: 'badge-green', label: '긍정' };
      if (v < -0.3) return { cls: 'badge-red', label: '부정' };
      return { cls: 'badge-blue', label: '중립' };
    },

    // 날짜 포맷
    fmtDate(s) {
      if (!s) return '-';
      try {
        const d = new Date(s);
        return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
      } catch (_) { return s; }
    },
  });
});
