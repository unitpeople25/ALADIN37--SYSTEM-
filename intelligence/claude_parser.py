"""
ALADIN37 - Claude Extractor
Phase 5 / Modul 1

Quelle-unabhängig: WhatsApp, E-Mail, Idealista, Makler-PDF, Exposé, Webseiten-Copy.
Nimmt rohen Text + Quelle entgegen, gibt strukturiertes JSON zurück.

Wichtig: Der Originaltext wird IMMER mit gespeichert (siehe pipeline.py),
damit spätere Widerspruchs-Checks möglich sind
(z.B. "Meerblick" im Text erwähnt, aber extracted.sea_view technisch
nicht verifizierbar -> Risikoindikator in broker_risk.py).
"""

import os
import json
import time
import urllib.request
import urllib.error

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-4-6"

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

EXTRACTION_SCHEMA_HINT = {
    "property_type": "str | null",
    "city": "str | null",
    "address": "str | null",
    "price": "number | null",
    "rooms": "int | null",
    "bathrooms": "int | null",
    "living_area": "number | null",
    "terrace": "bool | null",
    "sea_view": "bool | null",
    "year_built": "int | null",
    "energy_certificate": "str | null",
    "license": "str | null",
    "features": "list[str]",
}

SYSTEM_PROMPT = f"""Du bist der ALADIN37 Property Extractor.
Du bekommst Rohtext aus Immobilien-Inseraten, Makler-E-Mails, WhatsApp-Nachrichten
oder Exposés (meist Spanisch, Deutsch oder Englisch aus dem Mallorca-Immobilienmarkt).

Extrahiere ausschließlich Fakten, die im Text stehen. Erfinde nichts.
Wenn ein Feld nicht im Text vorkommt, setze es auf null.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt nach diesem Schema, ohne
Markdown-Codeblock, ohne Erklärtext davor oder danach:
{json.dumps(EXTRACTION_SCHEMA_HINT, ensure_ascii=False)}
"""


class ExtractionError(Exception):
    pass


def _call_claude(raw_text: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ExtractionError("ANTHROPIC_API_KEY ist nicht gesetzt.")

    body = json.dumps({
        "model": MODEL,
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": raw_text}
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    text_blocks = [b["text"] for b in payload.get("content", []) if b.get("type") == "text"]
    return "".join(text_blocks)


def extract(raw_input: dict, inbox_repo=None, inbox_id: int = None) -> dict:
    """
    raw_input: {"source": "idealista" | "whatsapp" | "email" | "makler_pdf" | ..., "text": "..."}

    Gibt strukturiertes Property-JSON zurück. Bei nicht behebbarem Fehler wird
    der Fehler (falls inbox_repo übergeben wurde) in der inbox-Tabelle
    protokolliert statt Daten stillschweigend zu verlieren (Phase 4-Prinzip:
    kein Datenverlust mehr).
    """
    raw_text = raw_input.get("text", "")
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw_response = _call_claude(raw_text)
            cleaned = raw_response.strip().strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

            extracted = json.loads(cleaned)
            extracted["_source"] = raw_input.get("source")
            extracted["_raw_text"] = raw_text
            return extracted

        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 429:
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue
            if 500 <= e.code < 600:
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue
            break  # 4xx (außer 429) macht ein Retry sinnlos

        except urllib.error.URLError as e:
            last_error = e
            time.sleep(RETRY_BACKOFF_SECONDS)
            continue

        except json.JSONDecodeError as e:
            last_error = e
            break  # Claude hat kein valides JSON geliefert - kein Retry-Kandidat

        except ExtractionError as e:
            last_error = e
            break

    error_message = f"Extraction fehlgeschlagen nach {attempt} Versuch(en): {last_error}"
    if inbox_repo is not None and inbox_id is not None:
        inbox_repo.mark_processed(inbox_id, error=error_message)

    raise ExtractionError(error_message)
