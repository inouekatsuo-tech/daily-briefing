"""
notifier.py — 全カテゴリから TOP5 を選んで Discord に通知する
"""
from __future__ import annotations

import logging

import httpx

from .fetcher import Article

logger = logging.getLogger(__name__)

# Discord Embed カラー（インディゴ）
EMBED_COLOR = 0x5865F2

_MEDALS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
_SCORE_EMOJI = {9: "🔥", 8: "⭐", 7: "✨", 6: "📌", 5: "📎"}


def send_discord(
    webhook_url: str,
    categories_data: list[dict],
    site_url: str,
    date_str: str,
) -> None:
    """
    全カテゴリの記事をスコア順に並べ、TOP5 を Discord Embed で送信する。
    """
    # 全記事をフラット化してスコア降順ソート
    all_articles: list[tuple[dict, Article]] = []
    for cat in categories_data:
        for article in cat.get("articles", []):
            all_articles.append((cat, article))

    if not all_articles:
        logger.warning("送信できる記事がありません")
        return

    top5 = sorted(all_articles, key=lambda x: x[1].score, reverse=True)[:5]

    archive_url = f"{site_url.rstrip('/')}/archive/{date_str}.html"

    # ── Embed の description 組み立て ────────────────────────────────────
    lines: list[str] = []
    for i, (cat, article) in enumerate(top5):
        score = article.score
        score_emoji = _SCORE_EMOJI.get(int(score), "📄")
        summary_short = article.summary[:90] + "…" if len(article.summary) > 90 else article.summary

        lines.append(
            f"{_MEDALS[i]} **{score_emoji} [{score:.1f}点]** {cat['emoji']} "
            f"[{article.title}]({article.url})"
        )
        if summary_short:
            lines.append(f"> {summary_short}")
        lines.append("")

    lines.append(f"📖 **[全文を読む → {date_str}]({archive_url})**")

    payload = {
        "embeds": [
            {
                "title": f"🌅 今日のTOP5ブリーフィング — {date_str}",
                "description": "\n".join(lines),
                "color": EMBED_COLOR,
                "footer": {"text": "Daily Briefing × Claude Haiku"},
            }
        ]
    }

    response = httpx.post(webhook_url, json=payload, timeout=30)
    response.raise_for_status()
    logger.info("Discord 通知送信完了")
