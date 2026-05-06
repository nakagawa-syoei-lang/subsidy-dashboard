# 補助金ダッシュボード (subsidy-dashboard)

中小企業向けの補助金・助成金情報を毎日自動収集し、静的サイトとして公開するプロジェクト。

## アーキテクチャ

```
GitHub Actions (daily_collect.yml)
  └─ python scripts/collect.py
       └─ 1都3県（東京・神奈川・埼玉・千葉）の自治体サイトをスクレイピング
            └─ docs/data.json に保存
                 └─ docs/index.html が読み込んで表示
```

## ファイル構成

```
.github/workflows/daily_collect.yml  # 毎日 00:00 UTC に実行する CI
scripts/collect.py                   # スクレイピング本体
docs/index.html                      # フロントエンド（フレームワーク不使用・単一ファイル）
docs/data.json                       # 収集データ（CI が自動コミット）
docs/last_updated.txt                # 最終更新日時
```

## ローカル実行

```bash
pip install requests beautifulsoup4 lxml
python scripts/collect.py
# docs/data.json と docs/last_updated.txt が更新される
```

ブラウザ確認は `docs/index.html` をそのまま開く（`data.json` は同階層の相対パスで fetch）。

## データフロー

- `collect.py` は `docs/data.json` に `{"updated":..., "count":..., "total":..., "items":[...]}` を書き出す
- `items` の各エントリ: `{id, title, org, pref, amount, deadline, target, category, url, source, date}`
- 期限切れ判定: `expired_by_age` フラグ または `start_date` から547日（1年半）経過
- 対象: 1都3県（東京都・神奈川県・埼玉県・千葉県）、自治体 + 国・省庁

## CI の挙動

- スケジュール: 毎日 00:00 UTC（日本時間 09:00）
- `workflow_dispatch` で手動実行可能
- 収集後、変更があれば `github-actions[bot]` として自動コミット・プッシュ
