#!/usr/bin/env bash
# adapters/hermes/scripts/apply-model-routing.sh — Claude と ChatGPT の両サブスクリプションを使い分ける設定（何度実行してもよい）
#
# 方針（スキル quota-aware-routing が運用手順の正本）:
#   - 指揮・判断・最終回答: Claude Opus（claude-subscription-directsdk-experimental、Claude Max の枠）
#   - サブエージェント: advanced-delegation の model_map。Claude 側のルート（Haiku / Sonnet / Opus）を優先する。
#     OpenAI（ChatGPT Plus の枠）は Claude の枠が逼迫したときの予備 openai-backup だけ。
#     逼迫時の振り替えは dotfiles-bridge が delegate_task の直前に自動で行う
#   - 裏方処理: タイトル・承認判定は Claude Haiku、圧縮は要約の質を優先して Claude Sonnet。
#     gpt-6-luna と速さに差がなかった（2026-11-24 実測、いずれも 3〜6 秒）ため、枠に余裕のある Claude に寄せる
#   - 片方が上限に達したとき: もう片方へ fallback
# モデル名は変わりやすい。週次の確認ジョブ（cron）が変更案を出し、承認後にこのファイルを直して再実行する。
set -euo pipefail
command -v hermes >/dev/null || { echo "hermes が見つかりません" >&2; exit 1; }

CLAUDE=claude-subscription-directsdk-experimental
CODEX=openai-codex

for p in "$CLAUDE" advanced-delegation; do
  [ -d "${HERMES_HOME:-$HOME/.hermes}/plugins/$p" ] || hermes plugins install "${p%-experimental}" >/dev/null
  hermes plugins enable "$p" >/dev/null
done

# メイン（オーケストレーター）
hermes config set model.provider "$CLAUDE"
hermes config set model.default 'claude-opus-5-5[1m]'
hermes config set --force agent.reasoning_effort medium  # 正しいキー（docs: Reasoning Effort）。検証器の誤警告を抑える
hermes config set fallback_providers "[{\"provider\": \"$CODEX\", \"model\": \"gpt-6.2-sol\"}]"

# サブエージェントのルート（オーケストレーターが名前と説明だけを見て選ぶ）
hermes config set delegation.backend model_map
hermes config set delegation.fallback_providers "[{\"provider\": \"$CODEX\", \"model\": \"gpt-6.2-sol\"}]"
hermes config set delegation.backends.model_map "$(cat <<JSON
{
  "default": "standard",
  "options": [
    {"name": "quick",
     "description": "Tier 1 (cheapest, Claude quota: Haiku). Lookups, short summaries, formatting, extraction from given text. Escalate to standard if the answer is thin or unverified.",
     "provider": "$CLAUDE", "model": "claude-haiku-5-5", "reasoning_effort": "low",
     "fallback_providers": [{"provider": "$CODEX", "model": "gpt-6-luna"}]},
    {"name": "standard",
     "description": "Tier 2 (default, Claude quota: Sonnet). Ordinary research, multi-step tool work, drafting, routine code. Escalate to deep if wrong, shallow, or unsupported by sources.",
     "provider": "$CLAUDE", "model": "claude-sonnet-5-5[1m]", "reasoning_effort": "medium",
     "fallback_providers": [{"provider": "$CODEX", "model": "gpt-6.2-sol"}]},
    {"name": "deep",
     "description": "Tier 3 (strongest, Claude quota: Opus, uses quota fastest). Hard analysis, design, debugging, careful review, conflicting sources. Use after standard failed or when stakes are high.",
     "provider": "$CLAUDE", "model": "claude-opus-5-5[1m]", "reasoning_effort": "high",
     "fallback_providers": [{"provider": "$CODEX", "model": "gpt-6.2-astra"}]},
    {"name": "openai-backup",
     "description": "Emergency only (OpenAI quota). Do not pick while Claude has room; the quota hook routes here automatically when Claude usage is high. Also for a second opinion after Claude routes failed twice.",
     "provider": "$CODEX", "model": "gpt-6.2-sol", "reasoning_effort": "medium",
     "fallback_providers": [{"provider": "$CLAUDE", "model": "claude-sonnet-5-5[1m]"}]}
  ]
}
JSON
)"

# 裏方処理も Claude へ
for t in title_generation:claude-haiku-5-5 approval:claude-haiku-5-5 compression:claude-sonnet-5-5; do
  hermes config set "auxiliary.${t%%:*}.provider" "$CLAUDE"
  hermes config set "auxiliary.${t%%:*}.model" "${t#*:}"
done

echo "モデルの使い分け設定を適用しました（新しいセッションから反映）。"
