/** 투자 자산 카테고리 */
export type AssetCategory =
  | 'finance'
  | 'realestate'
  | 'derivatives'
  | 'alternative'
  | 'private'
  | 'energy'
  | 'crowd'

/** 유동성 등급 */
export type Liquidity = 'instant' | 'days' | 'weeks' | 'months' | 'years'

/** 자산 상태 */
export type AssetStatus = 'available' | 'restricted' | 'upcoming'

/** 리스크 레벨 (1=보수 ~ 5=공격) */
export type RiskLevel = 1 | 2 | 3 | 4 | 5

/** 투자 자산 정의 */
export interface InvestmentAsset {
  id: string
  name: string
  category: AssetCategory
  min_capital: number
  min_capital_leveraged: number | null
  expected_return_min: number
  expected_return_max: number
  risk_level: RiskLevel
  liquidity: Liquidity
  leverage_available: boolean
  leverage_ratio: number | null
  leverage_type: string | null
  tax_benefit: string | null
  regulation_note: string | null
  status: AssetStatus
  upcoming_date: string | null
  beginner_friendly: boolean
  description: string
  caution: string | null
}

/** 자산 접근성 상태 */
export type AccessStatus = 'available' | 'insufficient' | 'conditional' | 'upcoming'

/** 카테고리 필터 옵션 */
export interface CategoryFilter {
  key: AssetCategory | 'all'
  label: string
}

/** 정렬 옵션 */
export type SortOption = 'return' | 'risk' | 'capital'

/** AI 어드바이저 포트폴리오 분석 모드 */
export type PortfolioMode = 'include' | 'ignore'

/** 마이너스통장 설정 (이자만 납입, 수시 상환 가능) */
export interface MinusLoanConfig {
  amount: number   // 원
  rate: number     // 연이율 %
}

/** 신용대출 설정 (고정금리, 원리금균등상환) */
export interface CreditLoanConfig {
  amount: number
  rate: number
  gracePeriod: number   // 거치기간 (개월)
  repayPeriod: number   // 상환기간 (개월)
}
