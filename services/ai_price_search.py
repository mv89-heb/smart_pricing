"""One-time AI-assisted price discovery using Gemini + Google Search grounding."""
import json
import os
import re
from decimal import Decimal, InvalidOperation
from google import genai
from google.genai import types


def _extract_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Gemini did not return JSON")
    return json.loads(text[start:end + 1])


def search_product_price(product_name, tag=None):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    client = genai.Client(api_key=api_key)
    identity = product_name if not tag else f"{product_name} ({tag})"
    prompt = f"""
אתה מנוע בדיקת מחירים עבור מערכת רכש בישראל.
חפש באינטרנט באמצעות Google Search את המחיר העדכני של המוצר הבא:
{identity}

כללים:
1. זהה את המוצר המדויק: יצרן, משקל/נפח/אריזה אם ניתן.
2. העדף מחיר רגיל ולא מחיר מבצע זמני.
3. העדף מקורות ישראליים אמינים ומחיר בשקלים כולל מע"מ כאשר ניתן.
4. אל תנחש. אם אין התאמה ברורה, found=false.
5. החזר JSON בלבד במבנה המבוקש.
confidence הוא מספר בין 0 ל-1.
"""
    response = client.models.generate_content(
        model=os.environ.get("GEMINI_PRICE_MODEL", "gemini-3.6-flash"),
        contents=prompt + "\nJSON: {\"found\":true,\"price\":12.34,\"currency\":\"ILS\",\"confidence\":0.93,\"matched_name\":\"...\",\"source_title\":\"...\",\"source_url\":\"https://...\",\"notes\":\"...\"}",
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.1),
    )
    data = _extract_json(response.text)
    found = bool(data.get("found"))
    try:
        price = float(Decimal(str(data.get("price")))) if found else None
    except (InvalidOperation, TypeError, ValueError):
        price = None
        found = False
    confidence = max(0.0, min(1.0, float(data.get("confidence") or 0)))
    if not found or price is None or price <= 0:
        return {"found": False, "confidence": confidence, "notes": str(data.get("notes") or "לא נמצא מחיר אמין")[:1000]}
    return {
        "found": True, "price": round(price, 2), "currency": data.get("currency", "ILS"),
        "confidence": confidence, "matched_name": str(data.get("matched_name") or product_name)[:200],
        "source_title": str(data.get("source_title") or "Google Search")[:200],
        "source_url": str(data.get("source_url") or "")[:1000],
        "notes": str(data.get("notes") or "")[:1000],
    }
