"""Download the configured siddur catalogs and texts into data/siddurim.json.

Run this occasionally when the local copy should be refreshed:
    python scripts/import_siddurim.py
"""

import json
import argparse
import sys
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "siddurim.json"
NUSACHIM = [
    "Siddur_Ashkenaz",
    "Siddur_Sefard",
    "Siddur_Edot_HaMizrach",
]


def flatten_text(data):
    if isinstance(data, str):
        return [data]
    if isinstance(data, list):
        result = []
        for item in data:
            result.extend(flatten_text(item))
        return result
    return []


VERIFY_SSL = True


def get_json(url, **kwargs):
    response = requests.get(url, timeout=20, verify=VERIFY_SSL, **kwargs)
    response.raise_for_status()
    return response.json()


def get_text(ref):
    encoded_ref = urllib.parse.quote(ref, safe="")
    data = get_json(
        f"https://www.sefaria.org/api/v3/texts/{encoded_ref}",
        params={"context": 0, "version": "hebrew"},
    )
    for version in data.get("versions", []):
        if str(version.get("language", "")).lower() in {"he", "heb", "hebrew"}:
            text = flatten_text(version.get("text"))
            if text:
                return text
    return []


def node_name(node):
    return node.get("enTitle") or node.get("key") or node.get("title")


def collect_refs(node, path, refs):
    for child in node.get("nodes", []):
        name = node_name(child)
        if not name:
            continue
        child_path = path + [name]
        if child.get("nodeType") == "JaggedArrayNode":
            refs.append(", ".join(child_path))
        elif child.get("nodes"):
            collect_refs(child, child_path, refs)


def main():
    global VERIFY_SSL
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="allow an untrusted local proxy certificate during import",
    )
    args = parser.parse_args()
    VERIFY_SSL = not args.insecure
    if args.insecure:
        requests.packages.urllib3.disable_warnings()

    catalog = {"schemas": {}, "texts": {}}
    for nusach in NUSACHIM:
        print(f"Loading {nusach} index...")
        index = get_json(f"https://www.sefaria.org/api/v2/index/{nusach}")
        schema = index.get("schema")
        if not schema:
            print(f"  no schema returned; skipping", file=sys.stderr)
            continue
        catalog["schemas"][nusach] = schema
        refs = []
        collect_refs(schema, [nusach.replace("_", " ")], refs)
        for number, ref in enumerate(refs, 1):
            try:
                text = get_text(ref)
                if text:
                    catalog["texts"][ref] = text
                print(f"  [{number}/{len(refs)}] {ref}")
            except requests.RequestException as error:
                print(f"  failed: {ref}: {error}", file=sys.stderr)
            time.sleep(0.05)

    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Saved {len(catalog['texts'])} prayers to {OUTPUT}")


if __name__ == "__main__":
    main()
