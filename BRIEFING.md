# 📋 Daily Briefing System

毎朝7時（バルセロナ時間）に5カテゴリの情報を自動キュレーションし、
GitHub Pages に公開 + Discord に TOP5 通知するシステム。

**PC 常時起動不要。GitHub Actions で完全自動化。**

---

## アーキテクチャ

```
GitHub Actions (UTC 5:00)
  → RSS フェッチ (feedparser)
  → Claude Haiku で日本語要約 + スコアリング
  → GitHub Pages に HTML 公開 (docs/)
  → Discord Webhook で TOP5 通知
```

---

## セットアップ手順

### 1. リポジトリ作成 & push

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<your-username>/daily-briefing.git
git push -u origin main
```

### 2. GitHub Pages を有効化

1. リポジトリの **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / Folder: `/docs`
4. Save → 数分後に `https://<your-username>.github.io/daily-briefing/` で公開

### 3. GitHub Secrets を設定

**Settings → Secrets and variables → Actions → Secrets**

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | Anthropic コンソールで取得 |
| `DISCORD_WEBHOOK_URL` | Discord サーバー設定 → インテグレーション → Webhook |

### 4. GitHub Variables を設定

**Settings → Secrets and variables → Actions → Variables**

| Name | Value |
|------|-------|
| `SITE_URL` | `https://<your-username>.github.io/daily-briefing` |

### 5. 動作確認（手動実行）

**Actions → Daily Briefing → Run workflow**

ログに "=== 完了 ===" が表示されれば成功。

---

## ソース管理

`config/sources.yaml` を編集するだけでソースを追加・削除できます。

Phase 2 では `sources.yaml` 内のコメントアウトを外すだけで5カテゴリに拡張できます。

---

## ローカルテスト

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export SITE_URL="https://your-username.github.io/daily-briefing"

python -m src.main

open docs/archive/$(date +%Y-%m-%d).html
```

---

## タイムゾーン

| 季節 | バルセロナ | UTC | cron |
|------|-----------|-----|------|
| 夏（4〜10月）| CEST = UTC+2 | 5:00 | `0 5 * * *` ✅ |
| 冬（11〜3月）| CET = UTC+1 | 6:00 | `0 6 * * *` に変更 |

---

## コスト目安

| 項目 | 概算 |
|------|------|
| Claude Haiku（5カテゴリ×15記事/日） | ~$0.01/日（月$0.30） |
| GitHub Actions | 無料枠内（月2000分） |
| GitHub Pages | 無料 |

**月 $1 以下で運用可能。**

---

## フェーズ計画

- ✅ **Phase 1**: カテゴリ1（健康）+ Discord + GitHub Pages
- ⬜ **Phase 2**: 残り4カテゴリを `sources.yaml` で有効化
- ⬜ **Phase 3**: 週次ダイジェスト / スタイル改善 / スコアトレンド
