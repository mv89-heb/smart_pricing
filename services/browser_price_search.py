"""One-time public-web price discovery using a real browser, without an API key.

This deliberately uses normal public Google result pages and does not bypass CAPTCHA,
login walls, robots controls, or other access restrictions. Results are advisory only.
"""
import re
import time
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def _money(text):
    if not text:
        return None
    matches = re.findall(r"(?:₪|ILS|ש[" + "חח" + r"]|NIS)\s*([0-9][0-9,]*(?:\.\d{1,2})?)|([0-9][0-9,]*(?:\.\d{1,2})?)\s*(?:₪|ILS|NIS)", text, re.I)
    values = []
    for a, b in matches:
        raw = (a or b).replace(',', '')
        try:
            value = float(raw)
            if 0 < value < 100000:
                values.append(value)
        except ValueError:
            pass
    return values[0] if values else None


def search_product_price(product_name, tag=None, page=None):
    identity = product_name if not tag else f"{product_name} {tag}"
    query = f'"{identity}" מחיר ישראל'
    own_browser = page is None
    playwright = browser = context = None
    try:
        if own_browser:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(locale="he-IL", timezone_id="Asia/Jerusalem")
            page = context.new_page()
        url = "https://www.google.com/search?q=" + quote_plus(query) + "&hl=iw&gl=il"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1200)
        title = (page.title() or "").lower()
        body = page.locator("body").inner_text(timeout=5000)
        if "unusual traffic" in body.lower() or "captcha" in title or "captcha" in body.lower():
            return {"found": False, "confidence": 0, "notes": "Google ביקש אימות או זיהה תעבורה חריגה; לא בוצע ניסיון לעקוף זאת."}
        links = page.locator("a").all()
        candidates = []
        for link in links[:80]:
            try:
                text = (link.inner_text() or "").strip().replace("\n", " ")
                href = link.get_attribute("href") or ""
                if not text or not href or not href.startswith("http"):
                    continue
                price = _money(text)
                if price is None:
                    parent_text = link.locator("xpath=..").inner_text(timeout=1000)
                    price = _money(parent_text)
                if price is not None:
                    candidates.append((price, text[:240], href))
            except Exception:
                continue
        if not candidates:
            price = _money(body)
            if price is None:
                return {"found": False, "confidence": 0, "notes": "לא נמצא מחיר בשקלים בתוצאות הציבוריות."}
            return {"found": True, "price": round(price, 2), "currency": "ILS", "confidence": 0.55, "matched_name": product_name, "source_title": "Google Search", "source_url": url, "notes": "מחיר שנמצא בדף תוצאות; מומלץ לאשר ידנית."}
        price, source_title, source_url = candidates[0]
        confidence = 0.72
        if len(candidates) >= 2 and abs(candidates[0][0] - candidates[1][0]) / max(candidates[0][0], 1) < 0.08:
            confidence = 0.84
        return {"found": True, "price": round(price, 2), "currency": "ILS", "confidence": confidence, "matched_name": product_name, "source_title": source_title, "source_url": source_url, "notes": "מחיר מחיפוש Google ציבורי; נדרשת בדיקה שהמוצר והאריזה תואמים."}
    except PlaywrightTimeoutError:
        return {"found": False, "confidence": 0, "notes": "החיפוש ארך יותר מדי זמן."}
    except Exception as exc:
        return {"found": False, "confidence": 0, "notes": f"שגיאת חיפוש: {str(exc)[:300]}"}
    finally:
        if own_browser:
            try:
                if context: context.close()
                if browser: browser.close()
                if playwright: playwright.stop()
            except Exception:
                pass


def search_products(products, progress=None):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(locale="he-IL", timezone_id="Asia/Jerusalem")
        page = context.new_page()
        try:
            for index, item in enumerate(products, 1):
                name = str(item.get("name") or "").strip()[:100]
                if not name:
                    continue
                result = search_product_price(name, str(item.get("tag") or "").strip()[:80], page=page)
                results.append({"name": name, "current_price": float(item.get("current_price") or 0), **result})
                if progress:
                    progress(index, len(products), name, result)
                time.sleep(1.0)
        finally:
            context.close()
            browser.close()
    return results
