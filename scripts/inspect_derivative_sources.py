"""Fetch only the six already-linked derivative lessons and inspect their examples."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('DefnOfDerivative', 'ProductQuotientRule', 'ChainRule', 'ImplicitDIff',
         'HigherOrderDerivatives', 'LinearApproximations')

def main():
    cache = ROOT / '.cache/phase3/paul'
    for page in PAGES:
        path = cache / f'CalcI-{page}.html'
        if not path.exists():
            url = f'https://tutorial.math.lamar.edu/Classes/CalcI/{page}.aspx'
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=45) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Page exceeds selective fetch limit')
            path.write_bytes(raw)
            path.with_suffix('.metadata.json').write_text(json.dumps(dict(
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                sha256=hashlib.sha256(raw).hexdigest())), encoding='utf-8')
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        print(page, flush=True)
        for example in soup.select('div.example'):
            header = BeautifulSoup(str(example), 'html.parser')
            for node in header.select('.example-content, .SH-Link'):
                node.decompose()
            print(header.get_text(' ', strip=True), flush=True)
            print('solution parts:', [node.get_text(' ', strip=True) for node in example.select('summary')], flush=True)

if __name__ == '__main__':
    main()
