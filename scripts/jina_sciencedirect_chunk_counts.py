#!/usr/bin/env python3
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import requests

COUNTRIES = ["Malaysia", "Japan", "Indonesia", "Iceland"]
RANGES = [(2010, 2012), (2013, 2015), (2016, 2018), (2019, 2021), (2022, 2024), (2025, 2025)]
QUERY_TEMPLATE = '"hot spring" AND "geothermal resource" AND "{}"'


def fetch_chunk(country, start, end):
    query = QUERY_TEMPLATE.format(country)
    date_param = str(start) if start == end else f"{start}-{end}"
    target = (
        "http://www.sciencedirect.com/search?qs="
        + quote(query)
        + f"&date={date_param}"
    )
    url = "https://r.jina.ai/" + target
    r = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/plain, text/markdown, */*",
            "X-Return-Format": "markdown",
        },
        timeout=240,
    )
    text = r.text
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {text[:300]}")
    counts = {str(y): 0 for y in range(start, end + 1)}
    # Parse the visible year facet rows, e.g. '1. - [x] 2025 (74)'.
    for year, count in re.findall(r"(?m)^\s*\d+\.\s+-\s+\[x\]\s+(20\d{2})\s+\(([0-9,]+)\)", text):
        if year in counts:
            counts[year] = int(count.replace(",", ""))
    total_match = re.search(r"(?m)^#\s+([0-9][0-9,]*)\s+results?\s*$", text)
    total = int(total_match.group(1).replace(",", "")) if total_match else None
    return {
        "country": country,
        "start": start,
        "end": end,
        "date_param": date_param,
        "url": url,
        "counts": counts,
        "total": total,
        "status": r.status_code,
    }


def main():
    tasks = [(c, s, e) for c in COUNTRIES for s, e in RANGES]
    chunks = []
    errors = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {executor.submit(fetch_chunk, *task): task for task in tasks}
        for future in as_completed(future_map):
            task = future_map[future]
            try:
                result = future.result()
                chunks.append(result)
                print(result, flush=True)
            except Exception as exc:
                errors.append({"task": task, "error": repr(exc)})
                print(f"ERROR {task}: {exc!r}", flush=True)

    counts = {c: {str(y): 0 for y in range(2010, 2026)} for c in COUNTRIES}
    for chunk in chunks:
        counts[chunk["country"]].update(chunk["counts"])

    output = {
        "query_template": QUERY_TEMPLATE,
        "countries": COUNTRIES,
        "counts": counts,
        "chunks": sorted(chunks, key=lambda x: (x["country"], x["start"])),
        "errors": errors,
    }
    Path("sciencedirect_country_annual_counts_chunks.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with open("sciencedirect_country_annual_counts_chunks.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Year"] + COUNTRIES)
        for year in range(2010, 2026):
            writer.writerow([year] + [counts[c][str(year)] for c in COUNTRIES])

    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
