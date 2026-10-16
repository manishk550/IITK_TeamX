from __future__ import annotations

"""Verified NIFTY 50 annual-report excerpts used for the development corpus.

Figures are normalized to INR crore. Source URLs point to official company
investor-relations material. The compact corpus keeps local development fast;
the same schema supports the required 500–2,000 document production corpus.
"""


from dataclasses import dataclass


@dataclass(frozen=True)
class Passage:
    document_id: str
    company: str
    ticker: str
    fiscal_period: str
    filing_type: str
    page: int
    section: str
    text: str
    source_url: str


def load_corpus() -> list[Passage]:
    """Return the development corpus."""
    raw = [
        ("RIL-AR-2024", "Reliance Industries", "RELIANCE", "FY2024", "Annual Report", 1, "Consolidated Financial Performance",
         "Revenue was ₹914,472 crore for fiscal 2024, revenue was ₹891,311 crore for fiscal 2023. Gross revenue was ₹1,000,122 crore for fiscal 2024 compared with ₹974,864 crore for fiscal 2023.",
         "https://www.ril.com/ar2023-24/financial-performance-and-review.html"),
        ("RIL-AR-2024", "Reliance Industries", "RELIANCE", "FY2024", "Annual Report", 2, "Risk Management",
         "Principal risks include commodity-price volatility, changes in regulation, cyber security, supply-chain disruption, project execution, competition, and geopolitical uncertainty.",
         "https://www.ril.com/ar2023-24/index.html"),
        ("TCS-AR-2024", "Tata Consultancy Services", "TCS", "FY2024", "Annual Report", 1, "FY2024 Business Highlights",
         "Revenue was ₹240,893 crore for fiscal 2024, revenue was ₹225,458 crore for fiscal 2023, and revenue was ₹191,754 crore for fiscal 2022. The reported operating margin was 24.6 percent in fiscal 2024.",
         "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/2023-24/ar/annual-report-2023-2024.pdf"),
        ("TCS-AR-2024", "Tata Consultancy Services", "TCS", "FY2024", "Annual Report", 2, "Business Risks",
         "Principal risks include macroeconomic uncertainty, geopolitical volatility, cyber security, currency movements, talent retention, technology disruption, and concentration in major markets.",
         "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/2023-24/ar/annual-report-2023-2024.pdf"),
        ("INFY-AR-2024", "Infosys", "INFY", "FY2024", "Annual Report", 1, "Three Year Financial Overview",
         "Revenue was ₹153,670 crore for fiscal 2024, revenue was ₹146,767 crore for fiscal 2023, and revenue was ₹121,641 crore for fiscal 2022. Operating income was ₹31,747 crore in fiscal 2024.",
         "https://www.infosys.com/investors/reports-filings/annual-report/annual-reports/ar-2023-24.html"),
        ("INFY-AR-2024", "Infosys", "INFY", "FY2024", "Annual Report", 2, "Basis of Preparation",
         "The consolidated financial statements are prepared in accordance with International Financial Reporting Standards as issued by the International Accounting Standards Board. Indian statutory statements are prepared under Ind AS.",
         "https://www.infosys.com/investors/reports-filings/quarterly-results/2023-2024/q4/ind-as.html"),
        ("HCLTECH-AR-2024", "HCLTech", "HCLTECH", "FY2024", "Annual Report", 1, "FY2024 Financial Results",
         "Revenue was ₹109,913 crore for fiscal 2024, revenue was ₹101,456 crore for fiscal 2023. Operating income was ₹20,027 crore in fiscal 2024. Net income was ₹15,702 crore in fiscal 2024.",
         "https://www.hcltech.com/press-releases/hcltech-reports-fy24-revenue-133-billion-54-yoy"),
        ("HCLTECH-AR-2024", "HCLTech", "HCLTECH", "FY2024", "Annual Report", 2, "Business Profile",
         "HCLTech operates across digital, engineering, cloud, AI, software, and business-process services. Its principal markets include the Americas, Europe, and the rest of the world.",
         "https://www.hcltech.com/investor-relations/key-facts-and-data"),
        ("WIPRO-AR-2024", "Wipro", "WIPRO", "FY2024", "Annual Report", 1, "Five Year Financial Performance",
         "Revenue was ₹89,794.3 crore for fiscal 2024, revenue was ₹90,934.8 crore for fiscal 2023, and revenue was ₹79,528.9 crore for fiscal 2022. Operating income was ₹13,609.9 crore in fiscal 2024.",
         "https://www.wipro.com/investors/last-5-years-data/"),
        ("WIPRO-AR-2024", "Wipro", "WIPRO", "FY2024", "Annual Report", 2, "FY2024 Results",
         "IT services operating margin was 16.1 percent for fiscal 2024. Large-deal bookings were US$4.6 billion and operating cash flow was ₹17,620 crore.",
         "https://www.wipro.com/content/dam/nexus/en/investor/quarterly-results/2023-2024/q4fy24/press-release-q4fy24.pdf"),
    ]
    return [Passage(*row) for row in raw]
