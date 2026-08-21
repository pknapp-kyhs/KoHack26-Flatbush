"""Local JSON storage for the siddur catalog and prayer text."""

import json
import urllib.parse
from pathlib import Path

import requests
from urllib3.exceptions import InsecureRequestWarning


DATA_FILE = Path(__file__).resolve().parent / "data" / "siddurim.json"
HEBREW_LANGUAGES = {"he", "heb", "hebrew"}
# The local development proxy uses its own certificate.  This keeps the app
# usable locally; production deployments should provide a trusted CA instead.
SEFARIA_VERIFY_SSL = False
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def load_catalog():
    if not DATA_FILE.exists():
        return {}
    try:
        with DATA_FILE.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_schema(nusach):
    return load_catalog().get("schemas", {}).get(nusach)


def get_text(ref):
    """Return locally stored segments for a Sefaria-style reference."""
    normalized_ref = ref.replace("_", " ")
    texts = load_catalog().get("texts", {})
    return next(
        (text for stored_ref, text in texts.items()
         if stored_ref.replace("_", " ") == normalized_ref),
        [],
    )


def flatten_text(data):
    if isinstance(data, str):
        return [data]
    if isinstance(data, list):
        return [segment for item in data for segment in flatten_text(item)]
    return []


def fetch_text(ref):
    encoded_ref = urllib.parse.quote(ref, safe="")
    try:
        response = requests.get(
            f"https://www.sefaria.org/api/v3/texts/{encoded_ref}",
            params={"context": 0, "version": "hebrew"},
            timeout=5,
            verify=SEFARIA_VERIFY_SSL,
        )
        response.raise_for_status()
        for version in response.json().get("versions", []):
            language = str(version.get("language", "")).lower()
            if language in HEBREW_LANGUAGES and version.get("text"):
                return flatten_text(version["text"])
    except (requests.RequestException, ValueError):
        pass
    return []


def fetch_schema(nusach):
    encoded_nusach = urllib.parse.quote(nusach, safe="")
    try:
        response = requests.get(
            f"https://www.sefaria.org/api/v2/index/{encoded_nusach}",
            timeout=5,
            verify=SEFARIA_VERIFY_SSL,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def _save(catalog):
    DATA_FILE.parent.mkdir(exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def save_schema(nusach, schema):
    catalog = load_catalog()
    catalog.setdefault("schemas", {})[nusach] = schema
    catalog.setdefault("texts", {})
    _save(catalog)


def save_text(ref, text):
    catalog = load_catalog()
    catalog.setdefault("schemas", {})
    catalog.setdefault("texts", {})[ref] = text
    _save(catalog)
