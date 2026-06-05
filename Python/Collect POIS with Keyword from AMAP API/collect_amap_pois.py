#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collect AMap / 高德 POIs with keyword search and save to CSV.

Default query:
    keywords = 加油站
    city     = 深圳

Output CSV columns:
    name,district,coordinates

Before running, set your key as an environment variable:
    macOS/Linux:
        export AMAP_KEY="your_web_service_api_key"
        export AMAP_PRIVATE_KEY="your_web_service_signature_private_key"  # optional

    Windows PowerShell:
        setx AMAP_KEY "your_web_service_api_key"
        setx AMAP_PRIVATE_KEY "your_web_service_signature_private_key"    # optional

Run:
    python collect_amap_pois.py --keywords 加油站 --city 深圳 --out shenzhen_gas_stations.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


AMAP_PLACE_TEXT_URL = "https://restapi.amap.com/v3/place/text"


def md5_hex(text: str) -> str:
    """Return lowercase MD5 hex digest using UTF-8."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def make_amap_sig(params: dict[str, Any], private_key: str) -> str:
    """
    Generate AMap Web Service API digital signature.

    AMap signature format:
        sig = MD5(sorted_query_string + private_key)

    The `sig` parameter itself must not be included when calculating the signature.
    """
    signing_params = {k: v for k, v in params.items() if k != "sig" and v is not None}
    sorted_items = sorted(signing_params.items(), key=lambda item: item[0])
    raw = "&".join(f"{k}={v}" for k, v in sorted_items) + private_key
    return md5_hex(raw)


def normalize_text(value: Any) -> str:
    """AMap sometimes returns [] for empty string fields; normalize to a string."""
    if value is None or value == []:
        return ""
    return str(value).strip()


def request_json(params: dict[str, Any]) -> dict[str, Any]:
    """Call AMap endpoint and return decoded JSON."""
    query = urlencode(params)
    url = f"{AMAP_PLACE_TEXT_URL}?{query}"
    req = Request(url, headers={"User-Agent": "python-amap-poi-collector/1.0"})

    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"AMap returned non-JSON response: {body[:300]}") from exc


def collect_pois(
    amap_key: str,
    keywords: str,
    city: str,
    private_key: str | None = None,
    citylimit: bool = True,
    offset: int = 20,
    max_pages: int = 50,
    sleep_seconds: float = 0.2,
) -> list[dict[str, str]]:
    """
    Collect POIs from AMap keyword search.

    AMap currently limits paged keyword-search retrieval to about 200 records
    per same request; with offset=20, max_pages=10 is the practical maximum.
    """
    if not amap_key:
        raise ValueError("AMAP_KEY is empty. Set it in your environment first.")

    if offset < 1 or offset > 25:
        raise ValueError("offset should be between 1 and 25. AMap recommends not exceeding 25.")

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for page in range(1, max_pages + 1):
        params: dict[str, Any] = {
            "key": amap_key,
            "keywords": keywords,
            "city": city,
            "citylimit": "true" if citylimit else "false",
            "output": "JSON",
            "offset": offset,
            "page": page,
            "extensions": "all",
        }

        if private_key:
            params["sig"] = make_amap_sig(params, private_key)

        data = request_json(params)

        if data.get("status") != "1":
            info = data.get("info", "UNKNOWN")
            infocode = data.get("infocode", "UNKNOWN")
            raise RuntimeError(f"AMap API failed on page {page}: {info} ({infocode})")

        pois = data.get("pois", [])
        if not pois:
            break

        for poi in pois:
            name = normalize_text(poi.get("name"))
            district = normalize_text(poi.get("adname"))
            coordinates = normalize_text(poi.get("location"))

            # Fallback if adname is missing.
            if not district:
                district = normalize_text(poi.get("district"))

            unique_key = (
                normalize_text(poi.get("id")) or name,
                district,
                coordinates,
            )
            if unique_key in seen:
                continue

            seen.add(unique_key)
            rows.append(
                {
                    "name": name,
                    "district": district,
                    "coordinates": coordinates,
                }
            )

        # If fewer results than requested came back, there are no more pages.
        if len(pois) < offset:
            break

        time.sleep(sleep_seconds)

    return rows


def write_csv(rows: list[dict[str, str]], output_path: str) -> None:
    """Write CSV using UTF-8 with BOM so Excel opens Chinese text correctly."""
    fieldnames = ["name", "district", "coordinates"]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect AMap POIs and save name,district,coordinates to CSV."
    )
    parser.add_argument("--keywords", default="加油站", help="POI keyword, default: 加油站")
    parser.add_argument("--city", default="深圳", help="City name/citycode/adcode, default: 深圳")
    parser.add_argument("--out", default="amap_pois.csv", help="Output CSV path")
    parser.add_argument("--offset", type=int, default=20, help="POIs per page, default: 20")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Maximum pages to fetch, default: 10 because AMap keyword search pages up to about 200 records",
    )
    parser.add_argument(
        "--no-citylimit",
        action="store_true",
        help="Do not restrict results strictly to the specified city",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep between page requests, default: 0.2",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    amap_key = os.getenv("AMAP_KEY", "").strip()
    private_key = os.getenv("AMAP_PRIVATE_KEY", "").strip() or None

    try:
        rows = collect_pois(
            amap_key=amap_key,
            keywords=args.keywords,
            city=args.city,
            private_key=private_key,
            citylimit=not args.no_citylimit,
            offset=args.offset,
            max_pages=args.max_pages,
            sleep_seconds=args.sleep,
        )
        write_csv(rows, args.out)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Saved {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
