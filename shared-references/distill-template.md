# distill テンプレート

タイトル＝ファイル名は可能な限り元のチャットセッションのタイトルと同じ。日付・"distill"・"Distill:" を含めない。

```markdown
---
type: distill
date: <YYYY-MM-DD>
ai: <codex|claude|gemini|chatgpt|magi>
domain: [<関係する領域。多値可>]
status: draft
sources: ["<会話URL もしくは [[log]]>"]
spawned: []
moc: <status: final で MOC へ委譲したら "[[topic MOC]]"。未委譲なら行ごと省略>
---

# <元のチャットセッションのタイトル>

<!-- status: final で MOC に委譲したら、ナビは MOC へ寄せ、冒頭に次の1行を置く: -->
> 成果の統合先: [[topic MOC]]

## 候補（番号を指定して選ぶメニュー）

### 1. [[候補概念A]]
- 要約: <2–4文。判断に足る最小限>
- 出自: <セッションのどの文脈で出たか>
- 状態: 未作成

### 2. [[候補概念B]]
- 要約: …
- 出自: …
- 状態: 未作成

## どう繋がるか（1–3文）
> <候補間の関係。詳細は各 atomic note 本文へ>
```

> `status` が `final` になり、トピックに MOC を作ったら（`obsidian-moc` スキル参照）、群別索引・図・全体像の語りは MOC へ委譲する。distill は出自記録（候補ごとの出自＋`date`/`ai`/`sources`/`spawned`）に徹し、MOC と同じ索引を二重メンテしない。関連する atomic note が3枚以上あるトピックでは MOC を作成／更新する。MOC を作らないのは、関連 atomic note が2枚以下、または3枚あっても同一トピックとして束ねる関係が薄いなどの特殊な場面に限る。
