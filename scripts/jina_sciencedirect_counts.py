#!/usr/bin/env python3
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

COUNTRIES = ["Malaysia", "Japan", "Indonesia", "Iceland"]
START_YEAR = 2010
END_YEAR = 2025
QUERY_TEMPLATE = '"hot spring" AND "geothermal resource" AND "{}"'


def fetch(country):
    query = QUERY_TEMPLATE.format(country)
    target = (
        "http://www.sciencedirect.com/search?qs="
        + quote(query)
        + f"&date={START_YEAR}-{END_YEAR}"
    )
    url = "https://r.jina.ai/" + target
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/plain, text/markdown, */*",
        "X-Return-Format": "markdown",
    }
    r = requests.get(url, headers=headers, timeout=180)
    text = r.text
    Path(f"jina_{country.lower()}.md").write_text(text, encoding="utf-8")
    years = {str(y): None for y in range(START_YEAR, END_YEAR + 1)}
    for y in range(START_YEAR, END_YEAR + 1):
        pats = [
            rf"(?m)^\s*{y}\s*\((\d[\d,]*)\)\s*$",
            rf"(?m)^\s*{y}\s+(\d[\d,]*)\s*$",
            rf"\b{y}\b[^\n]{{0,80}}?\b(\d[\d,]*)\b",
        ]
        for pat in pats:
            m = re.search(pat, text)
            if m:
                years[str(y)] = int(m.group(1).replace(",", ""))
                break
    return {
        "country": country,
        "query": query,
        "target": target,
        "jina_url": url,
        "status": r.status_code,
        "length": len(text),
        "excerpt": text[:3000],
        "years": years,
    }


def main():
    results = {}
    for country in COUNTRIES:
        try:
            results[country] = fetch(country)
        except Exception as e:
            results[country] = {"country": country, "error": repr(e)}
        time.sleep(3)
    Path("jina_sciencedirect_counts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
