import { host, useGatewayActivationEpoch, useQuery, useValue } from '@hermes/plugin-sdk'
import { useEffect } from 'react'
import { jsx } from 'react/jsx-runtime'

const ID = 'dotfiles-bridge'
const levels = ['unknown', 'ok', 'warn', 'high', 'critical']
const colors = ['--ui-text-tertiary', '--ui-text-secondary', '--dt-primary', '--dt-destructive', '--dt-destructive']

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
  const live = !query.isError && age >= 0 && age <= 900000 && data?.accounts
  const details = []
  let expired = false
  let severity = 0
  const text = [['claude', 'C', 'Current session'], ['openai', 'O', 'Session']].map(([key, label, session]) => {
    const account = live && data.accounts[key]
    const wins = (account?.windows ?? []).filter(w => Date.parse(w.resets) > now)
    const resetSinceSample = wins.length !== (account?.windows?.length ?? 0)
    expired ||= resetSinceSample
    const level = wins.length && !resetSinceSample ? account.level : 'unknown'
    severity = Math.max(severity, levels.indexOf(level))
    const current = wins.find(w => w.window === session)
    for (const w of wins) {
      const rate = w.burn_per_hour == null ? '速度未確定' : `+${w.burn_per_hour.toFixed(1)}%/h`
      const reset = new Date(w.resets).toLocaleString()
      details.push(`${key} ${w.window}: ${w.used}%・${rate}・リセット ${reset}`)
    }
    return `${label} ${current ? `${current.used}%` : '?'}`
  }).join(' · ') + (severity >= 2 ? ' ⚠' : '')
  const detail = live ? [expired ? 'リセット後の再判定を待っています。' : data.summary, ...details,
    `更新 ${new Date(data.updated_at * 1000).toLocaleTimeString()}`].join('\n') : '使用率は未取得、または15分以上前の観測です。'
  return jsx('button', {
    type: 'button', title: detail, 'aria-label': `クオータ使用率 ${text}。${detail}`,
    style: { color: `var(${colors[severity]})` }, className: 'px-1.5 tabular-nums',
    onClick: () => host.notify({ kind: 'info', title: 'クオータ使用率', message: detail }), children: text
  })
}

export default {
  id: ID, name: 'Quota',
  register(ctx) {
    ctx.register({ id: 'quota', area: 'statusBar.right', order: 130, render: () => jsx(QuotaChip, { ctx }) })
  }
}
