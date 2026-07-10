#!/usr/bin/env python3
import json
import re
import sys
import time
from urllib.parse import urlencode
from curl_cffi import requests

BASE = "https://www.sciencedirect.com"
API = BASE + "/search/api"
COUNTRIES = ["Malaysia", "Japan", "Indonesia", "Iceland", "New Zealand", "Italy", "Turkey", "Kenya"]
QUERY_TEMPLATE = '"hot spring" AND "geothermal resource" AND "{}"'
DATE_RANGE = "2010-2025"

session = requests.Session(impersonate="chrome124")
base_headers = {
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def get_count(country: str):
    query = QUERY_TEMPLATE.format(country)
    params = {"qs": query, "date": DATE_RANGE, "show": 25, "offset": 0}
    search_url = BASE + "/search?" + urlencode(params)
    r = session.get(search_url, headers=base_headers, timeout=45)
    print(f"PAGE {country}: {r.status_code} {len(r.text)}", flush=True)
    if r.status_code != 200:
        return {"country": country, "error": f"search page HTTP {r.status_code}"}
    m = re.search(r'"searchToken":"([^"]+)"', r.text)
    if not m:
        sample = re.sub(r"\s+", " ", r.text[:500])
        return {"country": country, "error": "searchToken not found", "sample": sample}
    token = m.group(1)
    api_params = dict(params)
    api_params.update({"t": token, "hostname": "www.sciencedirect.com"})
    headers = dict(base_headers)
    headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": search_url,
        "X-Requested-With": "XMLHttpRequest",
    })
    time.sleep(2)
    a = session.get(API + "?" + urlencode(api_params), headers=headers, timeout=45)
    print(f"API  {country}: {a.status_code} {len(a.text)}", flush=True)
    if a.status_code != 200:
        return {"country": country, "error": f"api HTTP {a.status_code}", "sample": a.text[:500]}
    try:
        data = a.json()
    except Exception:
        return {"country": country, "error": "non-JSON API response", "sample": a.text[:500]}
    total = data.get("resultsFound", data.get("totalResults"))
    years = data.get("facets", {}).get("years", [])
    return {
        "country": country,
        "query": query,
        "date": DATE_RANGE,
        "total": int(total) if total is not None else None,
        "year_facets": years,
    }


def main():
    results = []
    for c in COUNTRIES:
        try:
            results.append(get_count(c))
        except Exception as e:
            results.append({"country": c, "error": repr(e)})
        time.sleep(3)
    print("RESULT_JSON=" + json.dumps(results, ensure_ascii=False), flush=True)
    with open("sciencedirect_counts.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    if not any(r.get("total") is not None for r in results):
        sys.exit(2)

if __name__ == "__main__":
    main()
