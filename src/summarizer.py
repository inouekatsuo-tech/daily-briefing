"""
summarizer.py — Claude Haiku で記事を日本語要約 + スコアリング
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import anthropic

from .fetcher import Article

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── モデル設定 ──────────────────────────────────────────────────────────────
MODEL = "claude-haiku-4-5-20251001"

# ── ユーザープロファイル（パーソナライズの基準）────────────────────────────
_USER_PROFILE = """
- 48歳、日本人男性、バルセロナ在住
- 連続起業家。化粧品ブランド（イビサクリーム）を14億円で売却した経験あり
- 現在「カナエル」というBubble製の夢管理アプリを開発中。200億規模の事業を目指す
- 健康：身長185cm、体重82kg→79kg目標。ジムA/Bスプリット（筋肥大目的）、パデル実施
- スタイル：British heritage classic、イケオジ路線
- 主な関心：M&A・スタートアップ・AI・生産性・長寿・自己最適化・健康最適化

## 男性としての美学・哲学（スコアリングで特に重視）
- 「流されない男」でいたい。感情的に反応せず、自分の軸で動く
- 媚びない・下がらない・自己尊重を保つ振る舞いを日々意識している
- ストア哲学（マルクス・アウレリウス的）な精神的強さに共感
- PUAや小手先のテクニックではなく、内側から滲み出る品格・存在感・余裕を磨きたい
- 「かっこいい48歳」を体現したい。老いを言い訳にせず、むしろ円熟の魅力を最大化する
"""

# ── システムプロンプト ───────────────────────────────────────────────────────
_SYSTEM_PROMPT = f"""あなたは優秀な情報キュレーターです。
下記のユーザープロファイルに基づいて、与えられた記事を評価・要約してください。

## ユーザープロファイル
{_USER_PROFILE}

## 出力形式（必ずこの JSON 配列のみを返す。他のテキスト不要）
[
  {{
    "title": "元の記事タイトル（変更不可）",
    "summary": "3文以内の日本語要約（具体的・実践的に）",
    "score": 8.5,
    "reason": "このスコアの理由（1文、日本語）"
  }}
]

## スコアリング基準（0〜10）
- 10.0: 今すぐ行動できる、ユーザー目標に直結する最重要情報
-  8〜9: 高重要度。意思決定や行動計画に影響する
-  5〜7: 参考になるが優先度は中
-  2〜4: 関連性低い、または一般的すぎる
-  0〜1: 全く関係ない、広告・スパム的内容

## 注意
- JSON 配列の要素数は入力記事と同じにすること
- score は小数点1桁までの数値
- summary は具体的な数値・固有名詞を含めると良い
"""


# ── メイン関数 ──────────────────────────────────────────────────────────────

def summarize_category(articles: list[Article], client: anthropic.Anthropic) -> list[Article]:
    """
    1カテゴリ分の記事をまとめて Claude Haiku に送り、
    summary / score / score_reason を埋めて返す。
    API エラー時はデフォルト値を設定してフォールバック。
    """
    if not articles:
        return articles

    articles_text = _build_prompt_text(articles)

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": articles_text}],
        )
        raw = message.content[0].text.strip()
        results = _parse_json_response(raw)

        for i, result in enumerate(results):
            if i >= len(articles):
                break
            articles[i].summary = result.get("summary", "")
            articles[i].score = float(result.get("score", 5.0))
            articles[i].score_reason = result.get("reason", "")

        logger.info(f"  Haiku 要約完了: {len(articles)} 件")

    except Exception as exc:
        logger.error(f"  Haiku 要約失敗: {exc} — フォールバック使用")
        for article in articles:
            article.summary = article.description[:150] + "…" if article.description else ""
            article.score = 5.0
            article.score_reason = "要約取得失敗（フォールバック）"

    return articles


# ── ヘルパー ────────────────────────────────────────────────────────────────

def _build_prompt_text(articles: list[Article]) -> str:
    lines = ["以下の記事を評価・要約してください:\n"]
    for i, a in enumerate(articles, start=1):
        lines.append(f"[{i}]")
        lines.append(f"タイトル: {a.title}")
        lines.append(f"ソース: {a.source_name}")
        lines.append(f"URL: {a.url}")
        lines.append(f"内容: {a.description[:400]}")
        lines.append("")
    return "\n".join(lines)


def _parse_json_response(raw: str) -> list[dict]:
    """
    Claude の返答からJSON配列を抽出してパース。
    マークダウンコードブロックが含まれていても対応。
    """
    # ```json ... ``` or ``` ... ``` を剥がす
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)

    return json.loads(raw)
