'use client'
import { useState } from 'react'
import { toast } from 'sonner'
import { useWealthData } from '@/hooks/useWealthData'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { WealthLineChart } from '@/components/charts/WealthLineChart'
import { fmtKrw } from '@/lib/format'
import { SyncBadge } from '@/components/SyncBadge'

const ASSET_TYPES = ['부동산', '적금', '청약', '연금', '보험', '현금', '기타'] as const
type AssetType = (typeof ASSET_TYPES)[number]

const TYPE_COLOR: Record<string, string> = {
  부동산: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  연금: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  적금: 'bg-green-500/20 text-green-300 border-green-500/30',
  청약: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  보험: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  현금: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  기타: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
}

interface ExtraAsset {
  id: number
  name: string
  type: string
  current_value_krw: number
  monthly_deposit_krw: number
  is_fixed: boolean
  maturity_date: string | null
  note: string | null
}

interface AssetForm {
  name: string
  type: AssetType
  current_value_krw: string
  monthly_deposit_krw: string
  is_fixed: boolean
  maturity_date: string
  note: string
}

const EMPTY_FORM: AssetForm = {
  name: '', type: '기타', current_value_krw: '',
  monthly_deposit_krw: '0', is_fixed: false, maturity_date: '', note: '',
}

function toForm(a: ExtraAsset): AssetForm {
  return {
    name: a.name, type: a.type as AssetType,
    current_value_krw: String(a.current_value_krw),
    monthly_deposit_krw: String(a.monthly_deposit_krw),
    is_fixed: a.is_fixed, maturity_date: a.maturity_date ?? '', note: a.note ?? '',
  }
}

async function apiCall(url: string, method: string, body?: object) {
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status}`)
}

interface FormActionsProps {
  id?: number
  saving: boolean
  canSave: boolean
  deleteConfirm: number | null
  onSave: (id?: number) => void
  onCancel: () => void
  onDelete: (id: number) => void
}

function FormActions({ id, saving, canSave, deleteConfirm, onSave, onCancel, onDelete }: FormActionsProps) {
  return (
    <div className="flex items-center gap-2 mt-2.5">
      <button onClick={() => onSave(id)} disabled={saving || !canSave}
        className="px-3 py-1.5 bg-gold text-black text-xs font-semibold rounded hover:bg-gold/80 disabled:opacity-40 cursor-pointer transition-colors">
        {saving ? '저장 중…' : '저장'}
      </button>
      <button onClick={onCancel} className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-colors">
        취소
      </button>
      {id !== undefined && (
        <button onClick={() => onDelete(id)} disabled={saving}
          className={`ml-auto px-3 py-1.5 text-xs rounded cursor-pointer transition-colors ${
            deleteConfirm === id
              ? 'bg-red-500/20 text-red-400 border border-red-500/40 hover:bg-red-500/30'
              : 'text-muted-foreground hover:text-red-400'
          }`}>
          {deleteConfirm === id ? '정말 삭제?' : '삭제'}
        </button>
      )}
    </div>
  )
}

function AssetFormFields({ form, onChange }: { form: AssetForm; onChange: (p: Partial<AssetForm>) => void }) {
  return (
    <div className="grid grid-cols-2 gap-2 pt-3 border-t border-mc-border">
      <div className="col-span-2">
        <label className="text-[14px] text-muted-foreground">이름</label>
        <input className="w-full bg-mc-bg border border-mc-border rounded px-2.5 py-1.5 text-sm text-foreground mt-0.5 outline-none focus:border-gold/60"
          value={form.name} onChange={e => onChange({ name: e.target.value })} placeholder="자산명" />
      </div>
      <div>
        <label className="text-[14px] text-muted-foreground">유형</label>
        <select className="w-full bg-mc-bg border border-mc-border rounded px-2.5 py-1.5 text-sm text-foreground mt-0.5 cursor-pointer outline-none focus:border-gold/60"
          value={form.type} onChange={e => onChange({ type: e.target.value as AssetType })}>
          {ASSET_TYPES.map(t => <option key={t}>{t}</option>)}
        </select>
      </div>
      <div>
        <label className="text-[14px] text-muted-foreground">현재 가치 (원)</label>
        <input className="w-full bg-mc-bg border border-mc-border rounded px-2.5 py-1.5 text-sm text-foreground mt-0.5 outline-none focus:border-gold/60"
          type="number" value={form.current_value_krw} onChange={e => onChange({ current_value_krw: e.target.value })} placeholder="0" />
      </div>
      <div>
        <label className="text-[14px] text-muted-foreground">월 적립 (원)</label>
        <input className="w-full bg-mc-bg border border-mc-border rounded px-2.5 py-1.5 text-sm text-foreground mt-0.5 outline-none focus:border-gold/60"
          type="number" value={form.monthly_deposit_krw} onChange={e => onChange({ monthly_deposit_krw: e.target.value })} placeholder="0" />
      </div>
      <div>
        <label className="text-[14px] text-muted-foreground">만기일</label>
        <input className="w-full bg-mc-bg border border-mc-border rounded px-2.5 py-1.5 text-sm text-foreground mt-0.5 outline-none focus:border-gold/60"
          type="date" value={form.maturity_date} onChange={e => onChange({ maturity_date: e.target.value })} />
      </div>
      <div className="col-span-2">
        <label className="text-[14px] text-muted-foreground">메모</label>
        <input className="w-full bg-mc-bg border border-mc-border rounded px-2.5 py-1.5 text-sm text-foreground mt-0.5 outline-none focus:border-gold/60"
          value={form.note} onChange={e => onChange({ note: e.target.value })} placeholder="메모 (선택)" />
      </div>
      <div className="col-span-2 flex items-center gap-2">
        <input type="checkbox" id="is_fixed" checked={form.is_fixed}
          onChange={e => onChange({ is_fixed: e.target.checked })} className="cursor-pointer" />
        <label htmlFor="is_fixed" className="text-xs text-muted-foreground cursor-pointer">
          고정자산 (전세금 등 — 월 적립 제외)
        </label>
      </div>
    </div>
  )
}

export function WealthTab() {
  const { data, isLoading, mutate } = useWealthData()
  const [editingId, setEditingId] = useState<number | null>(null)
  const [isAdding, setIsAdding] = useState(false)
  const [form, setForm] = useState<AssetForm>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  if (isLoading) return <div className="text-muted-foreground text-sm p-4">로딩 중...</div>
  if (!data) return null

  const investPct = data.total_wealth_krw > 0 ? (data.investment_krw / data.total_wealth_krw) * 100 : 0

  function startEdit(a: ExtraAsset) {
    setIsAdding(false); setDeleteConfirm(null)
    setEditingId(a.id); setForm(toForm(a))
  }

  function startAdd() {
    setEditingId(null); setDeleteConfirm(null)
    setForm(EMPTY_FORM); setIsAdding(true)
  }

  function cancel() { setEditingId(null); setIsAdding(false); setDeleteConfirm(null) }

  const patchForm = (p: Partial<AssetForm>) => setForm(f => ({ ...f, ...p }))

  function buildPayload(f: AssetForm) {
    return {
      name: f.name.trim(), asset_type: f.type,
      current_value_krw: Number(f.current_value_krw) || 0,
      monthly_deposit_krw: Number(f.monthly_deposit_krw) || 0,
      is_fixed: f.is_fixed,
      maturity_date: f.maturity_date || null,
      note: f.note || null,
    }
  }

  async function handleSave(id?: number) {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      if (id !== undefined) {
        await apiCall(`/api/wealth/assets/${id}`, 'PUT', buildPayload(form))
      } else {
        await apiCall('/api/wealth/assets', 'POST', buildPayload(form))
      }
      await mutate(); cancel()
    } catch (e) {
      console.error('저장 실패:', e)
      toast.error('저장에 실패했습니다. 다시 시도해주세요.')
    } finally { setSaving(false) }
  }

  async function handleDelete(id: number) {
    if (deleteConfirm !== id) { setDeleteConfirm(id); return }
    setSaving(true)
    try {
      await apiCall(`/api/wealth/assets/${id}`, 'DELETE')
      await mutate(); cancel()
    } catch (e) {
      console.error('삭제 실패:', e)
      toast.error('삭제에 실패했습니다. 다시 시도해주세요.')
    } finally { setSaving(false) }
  }



  return (
    <div className="space-y-4">
      {/* 전재산 추이 차트 */}
      {data.wealth_history && data.wealth_history.length > 1 && (
        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-5">
            <CardTitle className="text-xs font-mono">Wealth History</CardTitle>
          </CardHeader>
          <CardContent className="px-3 pb-4">
            <WealthLineChart history={data.wealth_history} height={220} />
          </CardContent>
        </Card>
      )}

      <div className="lg:grid lg:grid-cols-[1fr_1.6fr] lg:gap-4 lg:items-start space-y-4 lg:space-y-0">
      {/* 전체 자산 Hero */}
      <Card className="bg-mc-card border-mc-border">
        <CardContent className="pt-5 pb-5 px-5">
          <div className="text-xs text-muted-foreground mb-1">
            전체 자산<SyncBadge timestamp={data.last_updated} />
          </div>
          <div className="text-3xl font-mono font-bold">
            {fmtKrw(data.total_wealth_krw)}<span className="text-lg font-normal text-muted-foreground ml-1">원</span>
          </div>
          <div className="flex gap-4 mt-3 text-xs font-mono text-muted-foreground">
            <span>투자 <span className="text-foreground font-semibold">{fmtKrw(data.investment_krw)}원</span></span>
            <span>비금융 <span className="text-foreground font-semibold">{fmtKrw(data.extra_assets_krw)}원</span></span>
          </div>
          <div className="flex h-2 rounded-full overflow-hidden mt-3 gap-px">
            <div style={{ width: `${investPct}%` }} className="bg-gold" />
            <div style={{ width: `${100 - investPct}%` }} className="bg-mc-border" />
          </div>
          <div className="flex gap-3 mt-1.5 text-[14px] text-muted-foreground">
            <span><span className="inline-block w-2 h-2 rounded-sm bg-gold mr-1" />투자 {investPct.toFixed(0)}%</span>
            <span><span className="inline-block w-2 h-2 rounded-sm bg-mc-border mr-1" />비금융 {(100 - investPct).toFixed(0)}%</span>
          </div>
        </CardContent>
      </Card>

      {/* 비금융 자산 CRUD */}
      <Card className="bg-mc-card border-mc-border">
        <CardHeader className="py-3 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-xs font-mono">비금융 자산</CardTitle>
            <button onClick={startAdd}
              className="text-xs text-gold hover:text-gold/80 cursor-pointer transition-colors px-2 py-1 rounded hover:bg-gold/10">
              + 추가
            </button>
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div>
            {((data.extra_assets ?? []) as ExtraAsset[]).map(a => (
              <div key={a.id} className="border-b border-mc-border last:border-0">
                <button
                  onClick={() => editingId === a.id ? cancel() : startEdit(a)}
                  className="flex items-center justify-between w-full py-3 cursor-pointer hover:bg-mc-bg/40 -mx-1 px-1 rounded transition-colors text-left"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`text-[14px] px-1.5 py-0.5 rounded border font-mono shrink-0 ${TYPE_COLOR[a.type] ?? 'bg-muted text-muted-foreground border-border'}`}>
                      {a.type}
                    </span>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{a.name}</div>
                      {a.monthly_deposit_krw > 0 && (
                        <div className="text-[14px] text-muted-foreground">월 +{fmtKrw(a.monthly_deposit_krw)}원</div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-2">
                    <span className="text-sm font-mono font-semibold">{fmtKrw(a.current_value_krw)}원</span>
                    <span className="text-muted-foreground text-[14px]">{editingId === a.id ? '▲' : '▷'}</span>
                  </div>
                </button>
                {editingId === a.id && (
                  <div className="pb-3">
                    <AssetFormFields form={form} onChange={patchForm} />
                    <FormActions id={a.id} saving={saving} canSave={!!form.name.trim()}
                      deleteConfirm={deleteConfirm} onSave={handleSave} onCancel={cancel} onDelete={handleDelete} />
                  </div>
                )}
              </div>
            ))}
          </div>

          {isAdding && (
            <div className="mt-2">
              <AssetFormFields form={form} onChange={patchForm} />
              <FormActions saving={saving} canSave={!!form.name.trim()}
                deleteConfirm={deleteConfirm} onSave={handleSave} onCancel={cancel} onDelete={handleDelete} />
            </div>
          )}

          {data.monthly_recurring_krw > 0 && !isAdding && editingId === null && (
            <div className="mt-3 pt-3 border-t border-mc-border text-xs text-muted-foreground font-mono">
              매월 <span className="text-gold font-semibold">{fmtKrw(data.monthly_recurring_krw)}원</span> 자동 적립 중
            </div>
          )}
        </CardContent>
      </Card>
      </div>
    </div>
  )
}
