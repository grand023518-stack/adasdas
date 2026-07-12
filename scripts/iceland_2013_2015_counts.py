#!/usr/bin/env python3
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
import requests

QUERY='"hot spring" AND "geothermal resource" AND "Iceland"'
YEARS=[2013,2014,2015]

def one(year):
    target='http://www.sciencedirect.com/search?qs='+quote(QUERY)+f'&date={year}'
    url='https://r.jina.ai/'+target
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','X-Return-Format':'markdown'},timeout=240)
    m=re.search(r'(?m)^#\s+([0-9][0-9,]*)\s+results?\s*$',r.text)
    return year, (int(m.group(1).replace(',','')) if m else None), r.status_code, r.text[:500]

with ThreadPoolExecutor(max_workers=3) as ex:
    rows=list(ex.map(one,YEARS))
Path('iceland_2013_2015_counts.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(rows)
