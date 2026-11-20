#!/usr/bin/env bash
# quota-alert.sh — cron（AI を使わないジョブ）用。どれかの枠が 80% 以上になったら1回だけ通知する。
exec python3 "$HOME/.hermes/scripts/quota-status.py" --alert "${QUOTA_ALERT_THRESHOLD:-80}" --notify
