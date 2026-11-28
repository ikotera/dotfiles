import { host, Popover, PopoverContent, PopoverTrigger, useGatewayActivationEpoch, useQuery, useValue } from '@hermes/plugin-sdk'
import { useEffect } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'dotfiles-bridge'
const levels = ['unknown', 'ok', 'warn', 'high', 'critical']
const colors = ['--ui-text-tertiary', '--ui-text-secondary', '--dt-primary', '--dt-destructive', '--dt-destructive']
// [キー, チップの略号, 表の名前, 5時間枠の名前, 週枠の名前]
const ACCOUNTS = [['claude', 'C', 'Claude', 'Current session', 'Current week'],
  ['openai', 'O', 'OpenAI', 'Session', 'Weekly']]
const STALE_MS = 900000

// 使用率の色。チップと同じ段階を5時間枠・週枠それぞれの閾値で付ける（quota.py の USAGE_THRESHOLDS）
function usedColor(used, weekly) {
  const [warn, high] = weekly ? [80, 90] : [60, 75]
  return `var(${used >= high ? '--dt-destructive' : used >= warn ? '--dt-primary' : '--ui-text-secondary'})`
}

function untilText(ms) {
  if (!(ms > 0)) return '—'
  const min = Math.round(ms / 60000)
  const d = Math.floor(min / 1440), h = Math.floor(min % 1440 / 60), m = min % 60
  return d ? `${d}日${h}時間` : h ? `${h}時間${m}分` : `${m}分`
}

function resetClock(iso, now) {
  const t = new Date(iso)
  const sameDay = t.toDateString() === new Date(now).toDateString()
  const hm = t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return sameDay ? hm : `${t.getMonth() + 1}/${t.getDate()} ${hm}`
}

const cell = { padding: '3px 8px', whiteSpace: 'nowrap' }
const head = { ...cell, fontWeight: 500, color: 'var(--ui-text-tertiary)', textAlign: 'left',
  borderBottom: '1px solid var(--ui-stroke-secondary)' }
const muted = { color: 'var(--ui-text-tertiary)' }

function QuotaTable({ rows, now }) {
  const body = []
  rows.forEach(({ name, windows }, i) => windows.forEach((w, j) => {
    const top = i > 0 && j === 0 ? { borderTop: '1px solid var(--ui-stroke-secondary)' } : {}
    body.push(jsxs('tr', { children: [
      jsx('td', { style: { ...cell, ...top, fontWeight: 500 }, children: j === 0 ? name : '' }),
      jsx('td', { style: { ...cell, ...top, ...muted }, children: w.label }),
      jsx('td', { style: { ...cell, ...top, textAlign: 'right', fontWeight: 600, color: w.data ? usedColor(w.data.used, w.weekly) : undefined },
        children: w.data ? `${Math.round(w.data.used)}%` : '?' }),
      jsx('td', { style: { ...cell, ...top, textAlign: 'right' }, children: w.data ? untilText(Date.parse(w.data.resets) - now) : '—' }),
      jsx('td', { style: { ...cell, ...top, ...muted, textAlign: 'right' }, children: w.data ? resetClock(w.data.resets, now) : '' })
    ] }, `${i}-${j}`))
  }))
  return jsxs('table', { style: { borderCollapse: 'collapse', width: '100%', fontVariantNumeric: 'tabular-nums' }, children: [
    jsx('thead', { children: jsxs('tr', { children: [
      jsx('th', { style: head, children: 'サービス' }), jsx('th', { style: head, children: '枠' }),
      jsx('th', { style: { ...head, textAlign: 'right' }, children: '使用率' }),
      jsx('th', { style: { ...head, textAlign: 'right' }, children: 'リセットまで' }),
      jsx('th', { style: { ...head, textAlign: 'right' }, children: '時刻' })
    ] }) }),
    jsx('tbody', { children: body })
  ] })
}

function QuotaChip({ ctx }) {
  const profile = useValue(host.state.profile)
  const epoch = useGatewayActivationEpoch()
  const query = useQuery({
    queryKey: [ID, 'quota', profile, epoch],
    queryFn: () => ctx.rest('/quota'),
    refetchInterval: 60000,
    retry: false
  })
  const { refetch, data, dataUpdatedAt } = query
  useEffect(() => host.onEvent('plugin.dotfiles-bridge.quota.updated', () => { void refetch() }), [refetch])

  // 同じ値を再取得しても15分を過ぎれば未知に戻す。値は残量でなく使用率。
  const now = Math.max(Date.now(), dataUpdatedAt)
  const age = now - (data?.updated_at ?? 0) * 1000
  const live = !query.isError && age >= 0 && age <= STALE_MS && data?.accounts
  let expired = false
  let severity = 0
  const rows = []
  const burns = []
  const text = ACCOUNTS.map(([key, label, name, session, week]) => {
    const account = live && data.accounts[key]
    const wins = (account?.windows ?? []).filter(w => Date.parse(w.resets) > now)
    const resetSinceSample = wins.length !== (account?.windows?.length ?? 0)
    expired ||= resetSinceSample
    const level = wins.length && !resetSinceSample ? account.level : 'unknown'
    severity = Math.max(severity, levels.indexOf(level))
    const find = n => wins.find(w => w.window === n)
    rows.push({ name, windows: [{ label: '5時間', weekly: false, data: find(session) },
      { label: '週', weekly: true, data: find(week) }] })
    const s = find(session)
    if (s?.burn_per_hour != null) {
      burns.push(`${name} 5時間 +${s.burn_per_hour.toFixed(0)}%/h → リセット時 ${Math.min(999, s.projected).toFixed(0)}%`)
    }
    return `${label} ${s ? `${Math.round(s.used)}%` : '?'}`
  }).join(' · ') + (severity >= 2 ? ' ⚠' : '')

  const changes = live ? Object.entries(data.mapping ?? {}).filter(([k, v]) => k !== v).map(([k, v]) => `${k} → ${v}`) : []
  const note = (style, children) => jsx('div', { style: { fontSize: 11, marginTop: 6, ...style }, children })
  const content = live
    ? [jsx(QuotaTable, { rows, now }, 't'),
      expired && note({ color: 'var(--dt-primary)' }, 'リセットされた枠があります。次の観測（3分以内）で更新されます。'),
      burns.length > 0 && note(muted, burns.join('　')),
      changes.length > 0 && note({ color: 'var(--dt-primary)' }, `委任の自動振替: ${changes.join('、')}`),
      note(muted, `更新 ${new Date(data.updated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}（3分ごと）`)]
    : [note({ marginTop: 0 }, '使用率は未取得、または15分以上前の観測です。')]

  // Popover はチップの外をクリックするか Esc を押すまで開いたまま（トーストのように自動で消えない）
  return jsxs(Popover, { children: [
    jsx(PopoverTrigger, { asChild: true, children: jsx('button', {
      type: 'button', 'aria-label': `クオータ使用率 ${text}`,
      style: { color: `var(${colors[severity]})` }, className: 'px-1.5 tabular-nums', children: text
    }) }),
    jsxs(PopoverContent, { side: 'top', align: 'end', style: { width: 'auto', minWidth: 320, fontSize: 12 }, children: [
      jsx('div', { style: { fontWeight: 600, marginBottom: 4, padding: '0 8px' }, children: 'クオータ使用率' }),
      jsxs('div', { children: content })
    ] })
  ] })
}

export default {
  // Capabilities の行名はこの name に置き換わる（plugin-packages.ts）。パッケージ名と揃えて探せるようにする
  id: ID, name: 'dotfiles-bridge',
  register(ctx) {
    ctx.register({ id: 'quota', area: 'statusBar.right', order: 130, render: () => jsx(QuotaChip, { ctx }) })
  }
}
