#!/usr/bin/env python3
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright

COUNTRIES = ["Malaysia", "Japan", "Indonesia", "Iceland"]
QUERY_TEMPLATE = '"hot spring" AND "geothermal resource" AND "{}"'
START_YEAR = 2010
END_YEAR = 2025


def normalize_years(raw):
    out = {str(y): 0 for y in range(START_YEAR, END_YEAR + 1)}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            year = item.get("value") or item.get("label") or item.get("key") or item.get("year")
            count = item.get("count") or item.get("results") or item.get("valueCount")
            if str(year) in out and count is not None:
                try:
                    out[str(year)] = int(count)
                except Exception:
                    pass
    elif isinstance(raw, dict):
        for k, v in raw.items():
            if str(k) in out:
                try:
                    out[str(k)] = int(v)
                except Exception:
                    pass
    return out


def extract_year_facets(obj):
    if not isinstance(obj, (dict, list)):
        return None
    if isinstance(obj, dict):
        # Common ScienceDirect response shapes
        facets = obj.get("facets")
        if isinstance(facets, dict):
            for key in ("years", "year", "publicationYears", "publicationYear"):
                if key in facets:
                    years = normalize_years(facets[key])
                    if any(years.values()):
                        return years
        for key in ("years", "yearFacet", "publicationYears"):
            if key in obj:
                years = normalize_years(obj[key])
                if any(years.values()):
                    return years
        for v in obj.values():
            found = extract_year_facets(v)
            if found:
                return found
    else:
        for v in obj:
            found = extract_year_facets(v)
            if found:
                return found
    return None


async def main():
    out_dir = Path("sd_artifacts")
    out_dir.mkdir(exist_ok=True)
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            locale="en-US",
            timezone_id="Asia/Kuala_Lumpur",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1200},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        for country in COUNTRIES:
            page = await context.new_page()
            captured = []

            async def on_response(response):
                url = response.url
                if "search" in url.lower() and response.status == 200:
                    ctype = response.headers.get("content-type", "")
                    if "json" in ctype:
                        try:
                            captured.append(await response.json())
                        except Exception:
                            pass

            page.on("response", on_response)
            query = QUERY_TEMPLATE.format(country)
            url = (
                "https://www.sciencedirect.com/search?qs="
                + quote(query)
                + f"&date={START_YEAR}-{END_YEAR}"
            )
            entry = {"country": country, "query": query, "url": url}
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=90000)
                entry["page_status"] = response.status if response else None
                await page.wait_for_timeout(20000)
                body_text = await page.locator("body").inner_text(timeout=30000)
                entry["body_excerpt"] = body_text[:2500]
                await page.screenshot(path=out_dir / f"{country.lower()}_page.png", full_page=True)
                (out_dir / f"{country.lower()}_page.html").write_text(
                    await page.content(), encoding="utf-8"
                )

                years = None
                for payload in captured:
                    years = extract_year_facets(payload)
                    if years:
                        break

                # Fallback: parse visible year/count pairs in page text.
                if not years:
                    years = {str(y): 0 for y in range(START_YEAR, END_YEAR + 1)}
                    for y in range(START_YEAR, END_YEAR + 1):
                        patterns = [
                            rf"\b{y}\b\s*\(?\s*([0-9][0-9,]*)\s*\)?",
                            rf"\b{y}\b[^\n]{{0,60}}?([0-9][0-9,]*)",
                        ]
                        for pat in patterns:
                            m = re.search(pat, body_text)
                            if m:
                                years[str(y)] = int(m.group(1).replace(",", ""))
                                break
                    if not any(years.values()):
                        years = None

                entry["years"] = years
                entry["captured_json_count"] = len(captured)
            except Exception as exc:
                entry["error"] = repr(exc)
            finally:
                results[country] = entry
                await page.close()

        await browser.close()

    Path("sciencedirect_annual_counts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
