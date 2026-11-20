# Hermes 専用スキル

Hermes の仕組み（プラグイン・cron・kanban・デスクトップの `::preview` 等）に依存し、他のエージェントでは使えないスキルを置く。
`adapters/hermes/setup.sh` が `skills.external_dirs` に登録するので、Hermes からは読み取り専用で見える。

- 他のエージェントでも使える手順は、ここではなくリポジトリ直下の `skills/` に置く。
- 1件ずつ `<スキル名>/SKILL.md` の形で置く（Hermes の SKILL.md 形式。frontmatter に `name` と `description`）。
