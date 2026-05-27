"""
main.py — デイリーブリーフィングシステム エントリーポイント

実行方法（プロジェクトルートから）:
  python -m src.main

環境変数:
  ANTHROPIC_API_KEY   (必須)
  DISCORD_WEBHOOK_URL (省略可: 未設定なら通知スキップ)
  SITE_URL            (省略可: GitHub Pages の URL)
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, timezone, timedelta
from pathlib import Path

import anthropic
import yaml

from .fetcher import fetch_all_categories
from .summarizer import summarize_category
from .publisher import publish
from .notifier import send_discord

# ── ロギング設定 ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── パス定数 ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
CONFIG_DIR = ROOT_DIR / "config"
TEMPLATES_DIR = ROOT_DIR / "templates"
DOCS_DIR = ROOT_DIR / "docs"


def main() -> None:
    logger.info("=== デイリーブリーフィング 開始 ===")

    # ── 環境変数チェック ────────────────────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    site_url = os.environ.get(
        "SITE_URL",
        "https://your-username.github.io/daily-briefing",
    )

    # ── 設定読み込み ────────────────────────────────────────────────────────
    config_path = CONFIG_DIR / "sources.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # ── Anthropic クライアント ──────────────────────────────────────────────
    client = anthropic.Anthropic(api_key=api_key)

    # ── 日付（バルセロナ時間 = CEST UTC+2 を考慮）──────────────────────────
    # GitHub Actions は UTC で動くが、表示日付はバルセロナ時間に合わせる
    barcelona_tz = timezone(timedelta(hours=2))  # 夏時間 CEST
    today = date.today()  # UTC 5:00 → CEST 7:00 なので日付は同じ
    date_str = today.strftime("%Y-%m-%d")
    logger.info(f"対象日: {date_str}")

    # ── 1. フェッチ ─────────────────────────────────────────────────────────
    logger.info("--- Step 1: RSS フェッチ ---")
    categories_data = fetch_all_categories(config)
    total_fetched = sum(len(c["articles"]) for c in categories_data)
    logger.info(f"合計 {total_fetched} 件取得")

    # ── 2. 要約 + スコアリング ──────────────────────────────────────────────
    logger.info("--- Step 2: Claude Haiku 要約 ---")
    for cat in categories_data:
        if cat["articles"]:
            logger.info(f"  カテゴリ: {cat['name']} ({len(cat['articles'])} 件)")
            cat["articles"] = summarize_category(cat["articles"], client)
            # スコア降順ソート
            cat["articles"].sort(key=lambda a: a.score, reverse=True)

    # ── 3. HTML 公開 ────────────────────────────────────────────────────────
    logger.info("--- Step 3: GitHub Pages 公開 ---")
    archive_path = publish(categories_data, DOCS_DIR, TEMPLATES_DIR, today)
    logger.info(f"公開完了: {archive_path.name}")

    # ── 4. Discord 通知 ─────────────────────────────────────────────────────
    logger.info("--- Step 4: Discord 通知 ---")
    if discord_webhook:
        try:
            send_discord(discord_webhook, categories_data, site_url, date_str)
        except Exception as exc:
            logger.error(f"Discord 通知失敗: {exc}")
    else:
        logger.warning("DISCORD_WEBHOOK_URL 未設定 — スキップ")

    logger.info("=== 完了 ===")


if __name__ == "__main__":
    main()
