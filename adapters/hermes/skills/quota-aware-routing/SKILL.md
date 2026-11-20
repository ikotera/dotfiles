---
name: quota-aware-routing
description: Use when delegating or quota is high. Route by difficulty; escalate.
version: 1.0.0
metadata:
  hermes:
    tags: [delegation, model-routing, quota, subscription, escalation]
    related_skills: [advanced-delegation:model-routing]
---

# Quota-aware routing（Claude と ChatGPT の両サブスクリプションの使い分け）

Hermes の指揮は Claude Opus（Claude Pro の枠）が担い、実作業はサブエージェントに任せる。サブエージェントは原則 OpenAI 側（ChatGPT Plus の枠）で動かし、どちらか一方の5時間枠・週枠だけが減らないようにする。設定の正本は `adapters/hermes/scripts/apply-model-routing.sh`、残量の確認は `adapters/hermes/scripts/quota-status.py`。

## いつ使うか
- `delegate_task` を使うとき（毎回）。
- 重い依頼（調査・長文作成・複数の手順・3件以上の並列作業）に入る前。
- サブエージェントの回答が不十分・不正確に見えるとき。
- 上限に近い、または上限に達したというエラーや通知が出たとき。
- コードの分割・実装を伴う作業では、作業の分割と台帳の記録に同梱スキル `advanced-delegation:model-routing` も読み込む。本スキルは残量の判断と、調査・文章作業での格上げの判定を加える。

## ルート（安い順。config の順序が格上げのはしごになる）
| ルート | モデル・エフォート | 枠 | 向く作業 |
|---|---|---|---|
| `quick` | gpt-6-luna・low | OpenAI | 検索・抽出・短い要約・整形 |
| `standard`（既定） | gpt-6.2-sol・medium | OpenAI | 通常の調査・下書き・複数の手順を踏む作業 |
| `deep` | gpt-6.2-astra・high | OpenAI（減りが速い） | 難しい分析・設計・食い違う情報源・レビュー |
| `claude-backup` | Claude Sonnet 5.5・medium | Claude | OpenAI 側の逼迫時・OpenAI 側で2回失敗したとき |

## 手順
1. **残量を見る**（重い依頼の前、または前回の確認から1時間以上たっているとき）
   `python3 ~/.hermes/scripts/quota-status.py`（AI を呼ばないので枠を使わない。数秒かかる）
2. **配分を決める**
   | 状況 | 対応 |
   |---|---|
   | 両方とも80%未満 | 通常どおり。実作業は OpenAI 側のルートへ |
   | Claude の5時間枠が80%以上 | 自分（Opus）で実作業をしない。要約・下書きも委任する。95%を超えそうなら、ユーザーにメインモデルを OpenAI 側へ切り替えるか尋ねる（`/model` で切り替えると、次の1回は会話全体を読み直し直す） |
   | OpenAI 側が80%以上 | `deep` を避ける。重要なものは `claude-backup`、軽いものは `quick` に回す |
   | 両方とも95%以上 | リセット時刻を示し、後回しにするか、最小限で続けるかを尋ねる |
   ChatGPT にリセット権が残っていても、自分では使わない（`/usage reset` はユーザーの判断に任せる）。
3. **ルートを選んで委任する**: `delegate_task` の各タスクの `option` に上表のルート名を指定する。依頼文には、目的・受け入れ条件（何がそろえば完了か）・情報源の明記を必ず入れる。
4. **回答を検証する**（サブエージェントの「完了」をそのまま信じない）。次のどれかに当てはまれば不合格とする。
   - 目的や受け入れ条件の一部に答えていない。
   - 根拠（URL・ファイル・実行結果）がない。または、主要な主張を1つ自分で確かめたら食い違った。
   - 内部で矛盾している、既知の事実と合わない、推測を断定している。
   - 本人が失敗や不確かさを認めている。
5. **原因で分けて対応する**（最大2段まで格上げする。1つのサブタスクにつき計3回まで）
   | 原因 | 対応 |
   |---|---|
   | 依頼文の不足・前提情報の欠落 | 依頼文を直し、**同じルート**でやり直す（格上げしない） |
   | 少しの抜けだけ | `delegate_task(action='continue')` で同じサブエージェントに追加の指示を出す |
   | 浅い・誤り・推論の失敗（モデルの力不足） | **1段上のルート**で再委任する。前回の回答の要点と、何が不十分だったかを依頼文に入れる（最初からやり直させない） |
   | ネットワーク・ツール・一時的なエラー | 同じルートで1回だけやり直す |
   `deep` でも不合格なら `claude-backup` で再委任するか、自分で仕上げる。重要度が高いのに解決しないときは、未解決であることを明示してユーザーに報告する。
6. **記録する**: 各試行（成功も含む）を同梱スキルの台帳に1行ずつ残す。次回以降のルートの提案に使われる。
   `python3 ~/.hermes/plugins/advanced-delegation/skills/model-routing/scripts/route_ledger.py add --class <research|summary|…> --difficulty <1-5> --route <ルート> --outcome pass|fail --attempt <n> [--cause model|spec|context|env|flaky] --task "<内容>" --evidence "<確認した方法と結果>"`
7. **報告する**: 格上げやり直しをしたときだけ、どのルートで何回やり直したかを1行添える。

## 落とし穴
- 1トークンあたりの安さではなく、合格するまでの総消費で判断する。やり直しが続くなら最初から1段上を選ぶ。
- 依頼文の不足を格上げで補わない。枠を浪費し、計画の穴を隠すことになる。
- ルートや予備の接続先の変更は新しいセッションから反映される。変更後は `route_ledger.py sync-routes` を実行する。
- Claude 側の上限で予備の接続先（gpt-6.2-sol）へ自動で切り替わるかは未検証。追加利用の設定が理由でプラグインが自分で止めた場合は、切り替わらない。
- 追加利用（extra usage）はオフのままにする。オンにすると、Opus の長文対応版などで請求が発生しうる。
- モデル名・上限・料金は頻繁に変わる。週次の確認ジョブ「subscription-review」が変更案を出す。反映はユーザーの承認後に、設定スクリプトを直して再実行する形で行う。

## 確認
- `hermes delegation config --show` に4つのルートが安い順に並んでいること。
- `python3 ~/.hermes/scripts/quota-status.py` で両方の使用率が出ること。
