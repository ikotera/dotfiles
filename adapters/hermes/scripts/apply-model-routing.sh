#!/usr/bin/env bash
# adapters/hermes/scripts/apply-model-routing.sh — Claude と ChatGPT の両サブスクリプションを使い分ける設定（何度実行してもよい）
#
# 方針（スキル quota-aware-routing が運用手順の正本）:
#   - 指揮・判断・最終回答: Claude Opus（claude-subscription-directsdk-experimental）
#   - サブエージェント: advanced-delegation の model_map。既定は OpenAI 側。難易度でルートを選び、不十分なら格上げして再委任
#   - 裏方処理（タイトル・圧縮・承認判定）: gpt-6-luna で Claude の枠を使わない
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
hermes config set delegation.fallback_providers "[{\"provider\": \"$CLAUDE\", \"model\": \"claude-sonnet-5-5[1m]\"}]"
hermes config set delegation.backends.model_map "$(cat <<JSON
{
  "default": "standard",
  "options": [
    {"name": "quick",
     "description": "Tier 1 (cheapest, OpenAI quota). Lookups, short summaries, formatting, extraction from given text. Escalate to standard if the answer is thin or unverified.",
     "provider": "$CODEX", "model": "gpt-6-luna", "reasoning_effort": "low"},
    {"name": "standard",
     "description": "Tier 2 (default, OpenAI quota). Ordinary research, multi-step tool work, drafting, routine code. Escalate to deep if wrong, shallow, or unsupported by sources.",
     "provider": "$CODEX", "model": "gpt-6.2-sol", "reasoning_effort": "medium"},
    {"name": "deep",
     "description": "Tier 3 (strongest OpenAI, uses quota fastest). Hard analysis, design, debugging, careful review, conflicting sources. Use after standard failed or when stakes are high.",
     "provider": "$CODEX", "model": "gpt-6.2-astra", "reasoning_effort": "high"},
    {"name": "claude-backup",
     "description": "Claude quota. Use only when OpenAI usage is high (>=80%) or OpenAI routes failed twice, or the task needs Claude specifically.",
     "provider": "$CLAUDE", "model": "claude-sonnet-5-5[1m]", "reasoning_effort": "medium",
     "fallback_providers": [{"provider": "$CODEX", "model": "gpt-6.2-sol"}]}
  ]
}
JSON
)"

# 裏方処理は OpenAI の軽量モデルへ
for t in title_generation compression approval; do
  hermes config set "auxiliary.$t.provider" "$CODEX"
  hermes config set "auxiliary.$t.model" gpt-6-luna
done

echo "モデルの使い分け設定を適用しました（新しいセッションから反映）。"
