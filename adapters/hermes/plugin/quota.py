"""使用率の観測値から残量の推移と委任先を求める。時計・ファイル・Hermes に依存しない。"""
from datetime import datetime

WINDOWS = {"claude": ("Current session", "Current week"), "openai": ("Session", "Weekly")}
OPTIONS = ("quick", "standard", "deep", "claude-backup")
LEVELS = ("unknown", "ok", "warn", "high", "critical")
USAGE_THRESHOLDS = ((60, 75, 90), (80, 90, 97))
PROJECT_WARN, PROJECT_HIGH = 85, 100
ETA_CRITICAL_MIN = 15
LOOKBACK_SEC, MIN_SPAN_SEC = 900, 300
STATE_TTL_SEC = 900


def reset_ts(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.timestamp() if dt.tzinfo is not None else 0
    except (AttributeError, ValueError, OSError, OverflowError):
        return 0


def valid_used(u):
    return type(u) in (int, float) and 0 <= u <= 100


def window_stats(row, history, now):
    reset = reset_ts(row.get("resets"))
    u = row.get("used")
    if reset <= now or not valid_used(u):
        return None
    # Claude の取得時刻由来の端数秒は呼ぶたびに変わる。同一リセットの判定は秒単位。
    prior = min((s for s in history if s['account'] == row['account'] and s['window'] == row['window']
                 and int(reset_ts(s['resets'])) == int(reset) and valid_used(s['used'])
                 and MIN_SPAN_SEC <= now - s['ts'] <= LOOKBACK_SEC),
                key=lambda s: s['ts'], default=None)
    b = max(0, (u - prior['used']) * 60 / (now - prior['ts'])) if prior else None
    minutes = (reset - now) / 60
    return dict(window=row['window'], used=u, resets=row['resets'], minutes_to_reset=minutes,
                burn_per_hour=b * 60 if b is not None else None,
                projected=u + b * minutes if b is not None else None,
                eta_exhaust_min=(100 - u) / b if b else None)


def window_level(w, weekly):
    warn, high, critical = USAGE_THRESHOLDS[weekly]
    used, p, eta = w['used'], w['projected'], w['eta_exhaust_min']
    if used >= critical or (eta is not None and eta < min(ETA_CRITICAL_MIN, w['minutes_to_reset'])):
        return 'critical'
    if used >= high or (p is not None and p >= PROJECT_HIGH):
        return 'high'
    if used >= warn or (p is not None and p >= PROJECT_WARN):
        return 'warn'
    return 'ok'


def routing(openai, claude, options=OPTIONS):
    both = openai == claude == 'critical'
    busy = claude in ('high', 'critical')
    mapping = {name: name for name in options}
    for name in mapping:
        target = name
        if openai == 'critical':
            target = 'quick' if both else 'claude-backup'
        elif openai in ('warn', 'high') and name == 'deep':
            target = 'standard' if busy else 'claude-backup'
        elif openai == 'high' and name == 'standard' and not busy:
            target = 'claude-backup'
        elif openai in ('ok', 'unknown') and name == 'claude-backup' and busy:
            target = 'standard'
        if target in mapping:
            mapping[name] = target
    return mapping, both


def summarize(accounts, mapping):
    parts = []
    for account, info in accounts.items():
        windows = {w['window']: w for w in info['windows']}
        words = []
        for name, label in zip(WINDOWS[account], ('5h', '週')):
            w = windows.get(name)
            value = f"{w['used']:g}%" if w else '?'
            if w and w['burn_per_hour'] is not None:
                value += f"（+{w['burn_per_hour']:.0f}%/h→予測 {min(999, w['projected']):.0f}%）"
            words.append(f'{label} {value}')
        parts.append(('Claude' if account == 'claude' else 'OpenAI') + ' ' + ' / '.join(words))
    changes = ', '.join(f'{k}→{v}' for k, v in mapping.items() if k != v)
    return '・'.join(parts) + (f' ⚠ 振替: {changes}' if changes else '')


def build_state(rows, history, now, options=OPTIONS) -> dict:
    windows = {account: [w for row in rows if row.get('account') == account and row.get('window') in labels
                         if (w := window_stats(row, history, now)) is not None]
               for account, labels in WINDOWS.items()}
    return state_from_windows(windows, now, options)


def state_from_windows(by_account, now, options) -> dict:
    accounts = {}
    for account, labels in WINDOWS.items():
        windows = by_account[account]
        level = max((window_level(w, w['window'] == labels[1]) for w in windows),
                    key=LEVELS.index, default='unknown')
        accounts[account] = dict(level=level, windows=windows)
    mapping, both = routing(accounts['openai']['level'], accounts['claude']['level'], options)
    return dict(updated_at=now, accounts=accounts, mapping=mapping, both_critical=both,
                summary=summarize(accounts, mapping))
