# 語彙定義 — Properties の単一の真実源（single source of truth）

> [!info] 使い方
> - frontmatter の キー・値は英語小文字（kebab-case） に固定する。日本語の読みは本文と `aliases` が持つ。機械が突き合わせる識別子は英語、人間が読む表現は本文、という分業。
> - 値はここに定義した 閉じた集合から選ぶ。無ければ勝手に類義語を作らず、このファイルに追記してから使う（新設はユーザーに提案）。
> - 集計（[[Bases]]）の主軸は `type` と `domain`。ここが揺れると集計が壊れる。

## type（必須・単一・固定）
| 値 | 意味 |
|---|---|
| `concept` | 1概念の atomic note |
| `distill` | セッションの索引＋候補メニュー |
| `log` | 生の対話ログ |
| `moc` | Map of Content（領域のハブ） |
| `daily` | 日次記録・ジャーナル |

## domain（concept は必須・単一 / distill・log・moc・daily は多値可）
索引・ハブ・日次記録である distill・log・moc・daily は複数領域にまたがるため多値可。daily は該当領域がなければ空配列にする。集計単位である concept は必ず1つ。
| 値 | 範囲 |
|---|---|
| `hardware` | コンピュータハードウェア |
| `linux` | Linux / サーバー管理 |
| `macos` | macOS |
| `windows` | Windows |
| `ios` | iOS / OS・デバイス関連全般 |
| `network` | ネットワーク・通信 |
| `electronics` | 電気・電子・電力 |
| `engineering` | 工学・設計・実装上の物理的制約 |
| `philosophy` | 哲学 |
| `physics` | 物理 |
| `geoscience` | 地球科学・地震・気象・氷河 |
| `aviation` | 航空・飛行・スカイスポーツ |
| `mathematics` | 数学 |
| `statistics` | 統計・確率推定・データ解析 |
| `biology` | 生物・生命科学 |
| `chemistry` | 化学・材料 |
| `medicine` | 医学・薬学 |
| `economics` | 経済・マクロ |
| `finance` | 金融・資産運用・金融工学 |
| `geopolitics` | 地政学 |
| `history` | 歴史・考古学 |
| `fiction` | 虚構作品の構造分析・物語論 |
| `llm` | LLM・大規模言語モデル |
| `machine-learning` | 機械学習・ディープラーニング |
| `data-science` | データ分析・可視化・統計実務 |
| `computer-science` | 計算機科学・アルゴリズム・データ構造 |
| `ai-workflow` | AI 運用・プロンプト |
| `automation` | 自動化・スクリプト |
| `python` | Python |
| `rust` | Rust |
| `dev` | その他言語・開発全般 |
| `cybersecurity` | 情報セキュリティ・認証・脆弱性 |
| `obsidian` | Obsidian の機能・運用 |
| `knowledge-base` | Knowledge Base 設計・運用 |
| `trading` | トレーディング |


## tags（任意・多値）
領域をまたぐ横断的な切り口。候補から選び、新規は追記。

| 値 | 範囲 |
|---|---|
| `linking` | Wikilink・バックリンクなどリンク構造 |
| `query` | Bases・検索・抽出条件 |
| `metadata` | frontmatter・Properties・構造化メタデータ |
| `structure` | 方程式体系・ノート体系・構造整理 |
| `plugin` | Obsidian プラグインなど拡張機能 |
| `editing` | テキスト編集操作 |
| `naming` | 命名規約・正準名・別名設計 |
| `security` | セキュリティ・安全性・防御設計 |
| `workflow` | 手順・運用フロー |
| `pattern` | 反復して現れる一般パターン |
| `config` | 設定・構成 |
| `troubleshooting` | 障害切り分け・原因推定・復旧 |
| `reverse-engineering` | 未知のバイナリ形式・非公開APIの挙動を観察・実験で解明する手法 |
| `formula` | 計算式・評価式・定量モデル |
| `model` | 現象を理解するための概念モデル |
| `neuroscience` | 神経科学・脳・神経回路・意識の神経相関 |
| `history` | 歴史的経緯・発見の流れ |
| `notation` | 記号・演算子・表記法 |
| `derivation` | 数式導出・極限操作・論理展開 |
| `probability` | 確率・統計・分布 |
| `stochastic-process` | ブラウン運動など時間発展する確率過程 |
| `vector-calculus` | ナブラ・発散・回転などベクトル解析 |
| `geometry` | 空間・曲率・計量・幾何学的理解 |
| `relativity` | 特殊相対論・一般相対論 |
| `electromagnetism` | 電場・磁場・電磁波・電磁誘導 |
| `cosmology` | 宇宙膨張・赤方偏移など宇宙論 |
| `circuit-analysis` | 回路素子・インピーダンス・周波数応答 |
| `power-integrity` | 電源品質・リップル・デカップリング・電源安定性 |
| `signal-integrity` | 波形品質・伝送品質・ノイズ余裕 |
| `communication` | 通信方式・信号線・プロトコル |
| `radio-propagation` | 自由空間損失・地面反射・回折・透過など電波が空間を伝わる過程 |
| `antenna` | アンテナと給電系の物理・設計（放射・指向性・偏波・整合・給電線） |
| `measurement` | 実測・比較測定・波形観測 |
| `control-system` | フィードバック制御・発振・安定性 |
| `risk-management` | 損失制御・リスク管理・ドローダウン |
| `portfolio-theory` | ポートフォリオ理論・資産配分 |
| `leverage` | レバレッジ・デレバレッジ・ポジション倍率 |
| `tail-risk` | ファットテール・ジャンプ・極端事象 |
| `market-regime` | 平時・危機時など市場状態の切り替わり |
| `market-microstructure` | 板・流動性・約定・価格インパクト |
| `performance-metric` | カルマーレシオなど運用成績指標 |
| `risk-metric` | マイクロモート・曝露量正規化など、リスクを測る単位と分母の設計 |
| `optimization` | 最適化・目的関数・制約条件 |
| `kb-structure` | Knowledge Base の構造・MOC・運用設計 |
| `terminal` | ターミナル・端末エミュレーション |
| `keyboard` | キー入力・ショートカット・入力イベント |
| `editor` | nano などエディタ操作 |
| `trading` | トレーディング領域を従タグとして補助的に示す場合 |
| `spec` | 仕様書・規約 |
| `distill` | distill ワークフロー |
| `atomic-notes` | atomic note 化 |
| `vocabulary` | 語彙定義 |

## status（type ごとに固定）
| type | 取りうる値 |
|---|---|
| `concept` | `seedling` → `growing` → `evergreen` |
| `distill` | `draft` → `final` |
| `log` | `raw` → `processed` |
| `moc` | `seedling` → `growing` → `evergreen` |
| `daily` | 使用しない |

## キー定義（concept）
`type` / `domain` / `tags` / `status` / `created` / `up` / `related` / `source` / `aliases`

- `up` … 上位概念（単一・任意）。`[[上位概念]]` の形で記載する。
- `related` … 隣接概念（多値・任意）。`[[隣接概念]]` の形で記載する。
- `source` … 出自（distill、元ノート、または会話URL）。
- `aliases` … 別名・略語・和英表記・読み（[[Wikilink]] 解決用。日本語可）。
- `updated` は使わない（変更履歴は git が持つ。手動更新は腐るため二重情報源にしない）。
- リンク値（`up`/`related`/`source`/`aliases`）の中身は日本語ノート名で可。英語に揃えるのはキーと `type`/`domain`/`tags`/`status` の値のみ。

## キー定義（distill）
`type` / `date` / `ai` / `domain`（多値可）/ `status` / `sources` / `spawned` / `moc`

- `sources` … 出自（会話URL or `[[log]]`、多値可）。
- `spawned` … この distill から materialize した atomic note の `[[Wikilink]]`（多値）。
- `moc` … `status: final` 後に成果を委譲した先のトピックハブ `[[topic MOC]]`（単一・任意。MOC 未作成なら省略）。

## キー定義（moc）
`type` / `domain`（多値可）/ `tags` / `status` / `created` / `sources` / `aliases`

- 領域のハブ。複数領域にまたがるため `domain` は多値可。
- `sources` … 束ねる対象の `[[distill]]` 群（多値・任意）。1トピックが複数セッションにまたがると複数になる。
- `status` … `seedling` → `growing` → `evergreen`（育てて維持するハブ）。
- 本文に構成要素ノードへの `[[Wikilink]]` を群ごとに整理して並べる（ハブとしての主目的）。
- distill と MOC は併用し軸が異なる（distill＝セッション軸の出自記録／MOC＝トピック軸の恒久ハブ／atomic note は両者が指す概念の単一の真実源）。詳細は `distill-atomic-workflow.md` と `moc-workflow.md`。

## キー定義（daily）
`type` / `date` / `domain`（多値可・該当なしは空配列）/ `tags` / `linked` / `journal`（任意）

- `type` は `daily`。
- `domain` と `tags` は、この日扱った主題を分類する場合のみ `vocabulary.md` の値から選ぶ。
- `linked` はその日の記録から参照するノートの `[[Wikilink]]`（多値）。
- `journal` はプラグイン連携などで必要な場合だけ使う任意キー。
- `status` と `updated` は使わない。
