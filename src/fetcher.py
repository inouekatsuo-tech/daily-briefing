"""
fetcher.py — RSS フィードから記事を取得する
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import feedparser
import httpx

logger = logging.getLogger(__name__)


# ── データモデル ────────────────────────────────────────────────────────────

@dataclass
class Article:
    title: str
    url: str
    description: str          # 元の説明文（HTMLタグ除去済み）
    published: Optional[datetime]
    source_name: str
    category_id: str
    # summarizer が後から埋める
    summary: str = ""
    score: float = 0.0
    score_reason: str = ""


# ── ユーティリティ ──────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """HTML タグを除去してプレーンテキストを返す"""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _parse_datetime(entry) -> Optional[datetime]:
    """feedparser の published_parsed / updated_parsed から datetime を生成"""
    for attr in ('published_parsed', 'updated_parsed'):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6])
            except Exception:
                pass
    return None


# ── メイン関数 ──────────────────────────────────────────────────────────────

def fetch_all_categories(config: dict) -> list[dict]:
    """
    sources.yaml の config を受け取り、
    カテゴリごとに記事リストを含む dict のリストを返す。

    返り値の構造:
    [
      {
        "id": "health",
        "name": "健康・モテ・トレーニング",
        "emoji": "💪",
        "articles": [Article, ...]
      },
      ...
    ]
    """
    results = []
    for category in config.get("categories", []):
        articles = _fetch_category(category)
        results.append({
            "id": category["id"],
            "name": category["name"],
            "emoji": category.get("emoji", "📰"),
            "articles": articles,
        })
    return results


def _fetch_category(category: dict) -> list[Article]:
    """1カテゴリ分の全ソースを取得してまとめて返す"""
    all_articles: list[Article] = []
    max_items = category.get("max_items_per_source", 3)

    for source in category.get("sources", []):
        try:
            articles = _fetch_source(source, category["id"], max_items)
            all_articles.extend(articles)
            logger.info(f"  [{source['name']}] {len(articles)} 件取得")
        except Exception as exc:
            # 1ソース失敗しても他は継続
            logger.warning(f"  [{source['name']}] 取得失敗: {exc}")

    return all_articles


def _fetch_source(source: dict, category_id: str, max_items: int) -> list[Article]:
    src_type = source.get("type", "rss")
    if src_type == "rss":
        return _fetch_rss(source, category_id, max_items)
    raise ValueError(f"未対応のソースタイプ: {src_type}")


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
}


def _fetch_rss(source: dict, category_id: str, max_items: int) -> list[Article]:
    # httpx で直接取得 → feedparser に渡す（User-Agent 問題・gzip 対応）
    try:
        resp = httpx.get(source["url"], headers=_HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception:
        # httpx 失敗時は feedparser 直接取得にフォールバック
        feed = feedparser.parse(source["url"])

    # bozo=1 でも記事が取れる場合があるのでそのまま継続
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"RSS パース失敗: {feed.bozo_exception}")

    articles: list[Article] = []
    for entry in feed.entries[:max_items]:
        # 説明文を取得（summary > content > description の優先順）
        raw_desc = ""
        if hasattr(entry, "summary"):
            raw_desc = entry.summary
        elif hasattr(entry, "content") and entry.content:
            raw_desc = entry.content[0].get("value", "")
        elif hasattr(entry, "description"):
            raw_desc = entry.description

        description = _strip_html(raw_desc)[:600]  # 長すぎるものは切る

        articles.append(Article(
            title=_strip_html(entry.get("title", "（タイトルなし）")),
            url=entry.get("link", ""),
            description=description,
            published=_parse_datetime(entry),
            source_name=source["name"],
            category_id=category_id,
        ))

    return articles
