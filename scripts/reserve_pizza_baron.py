"""
SevenRooms - Pizza Bar on 38th 自動予約スクリプト
対象: 2026年7月15日 11:30〜13:30 の空き枠
実行: 6月15日 深夜0時（JST）= 6月14日 15:00 UTC に実行
"""

import sys
import time
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/Users/katsuo/my-projects/sns-strategy/scripts/reserve_pizza_baron.log"),
    ],
)
log = logging.getLogger(__name__)

VENUE_URL  = "https://www.sevenrooms.com/reservations/motyopizzabaron38"
PARTY_SIZE = 2
# 希望時間帯 (11:30〜13:30 のスロットをこの順で試みる)
PREFERRED_TIMES = ["11:30 AM", "12:00 PM", "12:30 PM", "1:00 PM", "1:30 PM"]

FIRST_NAME = "Katsuo"
LAST_NAME  = "Inoue"
EMAIL      = "inouekatsuo@gmail.com"
PHONE      = "08031580885"

MAX_RETRIES        = 60   # 最大試行回数
RETRY_INTERVAL_SEC = 15   # 再試行間隔（秒）


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info(f"試行 {attempt}/{MAX_RETRIES}")
                page.goto(VENUE_URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1000)

                # ---- 人数を2名に設定（デフォルトが2名なら不要だが念のため） ----
                guest_btn = page.locator('[aria-controls="search-pill-guest-popover"]')
                guest_text = guest_btn.inner_text()
                if "2 Guests" not in guest_text:
                    log.info("人数を2名に変更中...")
                    guest_btn.click()
                    page.wait_for_timeout(500)
                    page.locator('[id="search-pill-guest-popover"] li').filter(has_text="2 Guests").click()
                    page.wait_for_timeout(500)

                # ---- 日付を7月15日に設定 ----
                log.info("日付を7月15日に設定中...")
                page.locator('[aria-controls="search-pill-date-popover"]').click()
                page.wait_for_timeout(500)

                # 現在表示月を確認し、必要なら次月へ
                for _ in range(3):
                    label = page.locator('.rdp-caption_label').first.inner_text()
                    if "July 2026" in label:
                        break
                    page.locator('button[name="next-month"]').first.click()
                    page.wait_for_timeout(300)

                # 7月15日のボタンをクリック（テキストが "15" のもの）
                july_15 = page.locator('button[name="day"]').filter(has_text="15").locator(
                    'xpath=ancestor-or-self::button[contains(@aria-label, "July 2026")]'
                ).first
                # シンプルな方法: July 2026 ヘッダー直下のグリッドで "15" を選ぶ
                july_15 = page.locator(
                    'button[name="day"]:not([disabled]):not(.rdp-day_outside)'
                ).filter(has_text="15")
                count = july_15.count()
                if count == 0:
                    # まだ枠が開いていない可能性 → disabledでも試みる
                    july_15 = page.locator('button[name="day"]').filter(has_text="15").nth(0)
                    log.warning("7月15日が disabled です。枠がまだ開いていない可能性があります。")
                july_15.first.click()
                page.wait_for_timeout(2000)

                # ---- 空き時間スロットを確認 ----
                log.info("空きスロットを探しています...")
                chosen = None
                for preferred_time in PREFERRED_TIMES:
                    selector = f'[data-test*="reservation-timeslot-button-{preferred_time}"]'
                    slot = page.locator(selector).first
                    if slot.count() > 0 and slot.is_visible():
                        log.info(f"スロット発見: {preferred_time}")
                        chosen = slot
                        break

                if chosen is None:
                    # data-test でのマッチが失敗した場合、ラベルテキストで探す
                    for preferred_time in PREFERRED_TIMES:
                        slot = page.locator('[data-test="time-slot-label"]').filter(has_text=preferred_time).first
                        if slot.count() > 0 and slot.is_visible():
                            log.info(f"スロット発見（ラベル）: {preferred_time}")
                            chosen = slot.locator("xpath=ancestor::button").first
                            break

                if chosen is None:
                    log.warning("希望時間帯のスロットなし。再試行します...")
                    page.wait_for_timeout(RETRY_INTERVAL_SEC * 1000)
                    continue

                # ---- スロット選択 ----
                chosen.click()
                page.wait_for_load_state("networkidle", timeout=20000)
                page.wait_for_timeout(1000)
                log.info("スロット選択完了。予約フォームへ...")

                # ---- 予約フォーム入力 ----
                log.info("ゲスト情報を入力中...")

                # 名前
                first_input = page.locator('input[name*="first" i], input[placeholder*="First" i], input[id*="first" i]').first
                first_input.fill(FIRST_NAME)

                last_input = page.locator('input[name*="last" i], input[placeholder*="Last" i], input[id*="last" i]').first
                last_input.fill(LAST_NAME)

                # メール
                page.locator('input[type="email"], input[name*="email" i]').first.fill(EMAIL)

                # 電話番号（+81 は事前選択済みを想定）
                phone_input = page.locator('input[type="tel"], input[name*="phone" i]').first
                phone_input.fill(PHONE)

                # ---- 予約確定ボタン ----
                log.info("予約を確定します...")
                confirm = page.locator(
                    'button[type="submit"], button:has-text("Reserve"), button:has-text("Complete Reservation"), button:has-text("Confirm")'
                ).first
                confirm.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # ---- 結果確認 ----
                screenshot_path = "/Users/katsuo/my-projects/sns-strategy/scripts/reservation_result.png"
                page.screenshot(path=screenshot_path)
                log.info(f"完了！スクリーンショット: {screenshot_path}")

                page_text = page.inner_text("body")
                if any(kw in page_text for kw in ["confirmed", "Confirmed", "confirmation", "予約完了", "予約確認"]):
                    log.info("予約成功が確認されました！")
                else:
                    log.warning("予約成功の文言が見つかりません。スクリーンショットを確認してください。")

                browser.close()
                return True

            except PlaywrightTimeoutError as e:
                log.error(f"タイムアウト: {e}")
                try:
                    page.screenshot(path=f"/Users/katsuo/my-projects/sns-strategy/scripts/error_{attempt}.png")
                except Exception:
                    pass
                page.wait_for_timeout(RETRY_INTERVAL_SEC * 1000)
            except Exception as e:
                log.error(f"エラー ({type(e).__name__}): {e}")
                try:
                    page.screenshot(path=f"/Users/katsuo/my-projects/sns-strategy/scripts/error_{attempt}.png")
                except Exception:
                    pass
                page.wait_for_timeout(RETRY_INTERVAL_SEC * 1000)

        log.error(f"最大試行回数 ({MAX_RETRIES}) に達しました。予約できませんでした。")
        browser.close()
        return False


if __name__ == "__main__":
    log.info("=== Pizza Bar on 38th 予約スクリプト開始 ===")
    success = run()
    sys.exit(0 if success else 1)
