#!/usr/bin/env python3
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

COUNTRIES = ["Malaysia", "Japan", "Indonesia", "Iceland"]
YEARS = list(range(2010, 2026))
QUERY_TEMPLATE = '"hot spring" AND "geothermal resource" AND "{}"'


def fetch_count(session, country, year):
    query = QUERY_TEMPLATE.format(country)
    target = (
        "http://www.sciencedirect.com/search?qs="
        + quote(query)
        + f"&date={year}"
    )
    url = "https://r.jina.ai/" + target
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/plain, text/markdown, */*",
        "X-Return-Format": "markdown",
    }
    r = session.get(url, headers=headers, timeout=180)
    text = r.text
    if r.status_code != 200:
        return None, {"status": r.status_code, "excerpt": text[:500], "url": url}
    match = re.search(r"(?m)^#\s+([0-9][0-9,]*)\s+results?\s*$", text)
    if not match:
        match = re.search(r"\b([0-9][0-9,]*)\s+results?\b", text)
    if not match:
        return None, {"status": r.status_code, "excerpt": text[:1000], "url": url}
    return int(match.group(1).replace(",", "")), {"status": r.status_code, "url": url}


def main():
    session = requests.Session()
    counts = {country: {} for country in COUNTRIES}
    metadata = {}

    for country in COUNTRIES:
        for year in YEARS:
            key = f"{country}-{year}"
            try:
                count, meta = fetch_count(session, country, year)
                counts[country][str(year)] = count
                metadata[key] = meta
                print(f"{country} {year}: {count}", flush=True)
            except Exception as exc:
                counts[country][str(year)] = None
                metadata[key] = {"error": repr(exc)}
                print(f"{country} {year}: ERROR {exc!r}", flush=True)
            time.sleep(1.2)

    result = {
        "query_template": QUERY_TEMPLATE,
        "years": YEARS,
        "countries": COUNTRIES,
        "counts": counts,
        "metadata": metadata,
    }
    Path("sciencedirect_country_annual_counts.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with open("sciencedirect_country_annual_counts.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Year"] + COUNTRIES)
        for year in YEARS:
            writer.writerow([year] + [counts[c].get(str(year)) for c in COUNTRIES])

    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
