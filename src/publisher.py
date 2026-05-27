"""
publisher.py — Jinja2 テンプレートで HTML を生成し docs/ へ書き出す
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


def publish(
    categories_data: list[dict],
    docs_dir: Path,
    templates_dir: Path,
    today: date,
) -> Path:
    """
    1. docs/archive/YYYY-MM-DD.html を生成
    2. docs/index.html を最新日付に更新
    3. 生成した archive ファイルのパスを返す
    """
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )

    archive_dir = docs_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    date_str = today.strftime("%Y-%m-%d")
    archive_path = archive_dir / f"{date_str}.html"

    # ── archive/YYYY-MM-DD.html ────────────────────────────────────────────
    template = env.get_template("daily.html.j2")
    html = template.render(
        date_str=date_str,
        categories=categories_data,
    )
    archive_path.write_text(html, encoding="utf-8")
    logger.info(f"Archive published: {archive_path}")

    # ── index.html ──────────────────────────────────────────────────────────
    recent_archives = sorted(
        [p.stem for p in archive_dir.glob("????-??-??.html")],
        reverse=True,
    )[:14]  # 最新14日分

    index_template = env.get_template("index.html.j2")
    index_html = index_template.render(
        latest_date=date_str,
        recent_dates=recent_archives,
    )
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    logger.info("index.html updated")

    return archive_path
