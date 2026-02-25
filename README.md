# 補助金・助成金 情報ダッシュボード
### GitHub Pages × GitHub Actions で毎日自動更新

---

## 📁 ファイル構成

```
(リポジトリ名)/
├── .github/
│   └── workflows/
│       └── daily_collect.yml   ← 毎日自動実行の設定
├── docs/
│   ├── index.html              ← Webページ本体
│   └── data.json               ← 収集データ（自動更新）
├── scripts/
│   └── collect.py              ← 収集スクリプト
└── README.md
```

---

## 🚀 セットアップ手順（15分で完了）

### ① GitHubにリポジトリを作成

1. https://github.com/new を開く
2. Repository name: `subsidy-dashboard`（任意）
3. **Public** を選択（GitHub Pages無料利用のため）
4. 「Create repository」をクリック

### ② ファイルをアップロード

1. 作成したリポジトリのページで「uploading an existing file」をクリック
2. 以下の構造でファイルをドラッグ＆ドロップしてアップロード：
   - `.github/workflows/daily_collect.yml`
   - `docs/index.html`
   - `docs/data.json`
   - `scripts/collect.py`
3. 「Commit changes」をクリック

### ③ GitHub Pages を有効化

1. リポジトリの「Settings」タブを開く
2. 左メニュー「Pages」をクリック
3. Source: **Deploy from a branch**
4. Branch: **main** ／ Folder: **`/docs`**
5. 「Save」をクリック

数分後に `https://（ユーザー名）.github.io/subsidy-dashboard/` でアクセス可能になります。

### ④ 動作確認（手動で初回実行）

1. リポジトリの「Actions」タブを開く
2. 左の「毎日補助金情報を収集・公開」をクリック
3. 「Run workflow」→「Run workflow」ボタンをクリック
4. 数分後に緑チェックになれば成功 ✅

---

## 📅 自動更新スケジュール

毎日 **日本時間 09:00** に自動実行されます。
手動実行したい場合は Actions タブから「Run workflow」で即時実行できます。

---

## 🔗 社内Wikiへの共有方法

公開されたURLを社内Wikiやチャットに貼るだけです。

```
補助金・助成金ダッシュボード（毎日自動更新）
https://（ユーザー名）.github.io/subsidy-dashboard/
```

---

## ⚠️ 注意事項

- 掲載情報は参考情報です。申請前に必ず公式ページをご確認ください。
- リポジトリを **Private** にすると GitHub Pages が有料プランになります（Publicのままを推奨）。
- 社外からもアクセス可能なURLになります。機密情報は掲載しないでください。
