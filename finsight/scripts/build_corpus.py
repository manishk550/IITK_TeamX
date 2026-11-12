"""Download official annual reports and write data/corpus/pages.jsonl.

The verified metric cards in finsight.corpus stay separate. This script only
adds page text extracted from the downloaded PDFs. It does not invent figures.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data" / "corpus" / "pages.jsonl"
DOWNLOADS = Path("/tmp/finsight-pdfs")
SOURCES = [
    ("ril.pdf", "RIL-AR-2024", "Reliance Industries", "RELIANCE", "https://www.ril.com/ar2023-24/pdf/consolidated.pdf"),
    ("tcs.pdf", "TCS-AR-2024", "Tata Consultancy Services", "TCS", "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/2023-24/ar/annual-report-2023-2024.pdf"),
    ("infosys.pdf", "INFY-AR-2024", "Infosys", "INFY", "https://www.infosys.com/investors/reports-filings/annual-report/annual/documents/infosys-ar-24.pdf"),
    ("wipro.pdf", "WIPRO-AR-2024", "Wipro", "WIPRO", "https://www.wipro.com/content/dam/nexus/en/investor/annual-reports/2023-2024/integrated-annual-report-2023-24.pdf"),
]


def main() -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    rows = []
    for filename, document_id, company, ticker, url in SOURCES:
        target = DOWNLOADS / filename
        if not target.exists():
            urllib.request.urlretrieve(url, target)
        text = subprocess.check_output(["pdftotext", "-layout", str(target), "-"], text=True, errors="replace")
        for index, page in enumerate(text.split("\f"), start=1):
            cleaned = " ".join(page.split())
            if len(cleaned) < 280:
                continue
            rows.append({
                "document_id": document_id,
                "company": company,
                "ticker": ticker,
                "fiscal_period": "FY2024",
                "filing_type": "Annual Report",
                "page": index,
                "section": f"Page {index}",
                "text": cleaned[:2200],
                "source_url": url,
                "priority": 0,
            })
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with DESTINATION.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} pages to {DESTINATION}")


if __name__ == "__main__":
    main()
