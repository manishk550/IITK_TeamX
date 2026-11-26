from __future__ import annotations
from typing import Optional, Union



"""Planner, executor, and critic workflow with explicit safety limits."""


import re
import time
import uuid
from dataclasses import dataclass, field

from finsight.schemas import Citation, CopilotResponse, ToolCallRecord
from finsight.tools import ToolRegistry


REFUSAL_PATTERNS = [
    (re.compile(r"\b(buy(?:ing)?|sell|hold)\b.{0,40}\b(stock|shares|recommendation)\b|\bshould i (buy|sell|hold)\b", re.I),
     "FinSight cannot provide investment advice or a buy, sell, or hold recommendation."),
    (re.compile(r"\b(guarantee|predict|price target|will revenue be)\b", re.I),
     "Future performance cannot be presented as fact."),
    (re.compile(r"\b(personal account|social security|password|private information|aadhaar|pan card|personal phone|mobile number|personal email)\b", re.I),
     "FinSight cannot request or reveal personal or non-public information."),
    (re.compile(r"\bignore (all|the|previous|filings|citations|safety)\b|\bsystem override\b|\breveal the (hidden|system) prompt\b", re.I),
     "Instructions to bypass evidence or safety rules are refused."),
]

OUTSIDE_CORPUS = ("hdfc", "itc", "asian paints")
INSTRUCTION = re.compile(r"\b(system override|ignore all safety|buy .{0,30}shares)\b", re.I)
STATED_MARGIN = re.compile(
    r"operating margin was (?P<pct>[0-9]+(?:\.[0-9]+)?) percent(?: (?:in|for) fiscal (?P<year>20[0-9]{2}))?",
    re.I,
)
# A fiscal year named in a question: "FY2026", "FY 26", "FY'27", "fiscal 2026", "fiscal year 2026", "in 2026".
YEAR_MENTION = re.compile(r"\bFY\s*'?(?P<fy>[0-9]{4}|[0-9]{2})\b|\b(?P<year>(?:19|20)[0-9]{2})\b", re.I)
DEFAULT_LATEST_YEAR = "2024"

COMPANIES = {
    "reliance": "Reliance Industries",
    "ril": "Reliance Industries",
    "tata consultancy services": "Tata Consultancy Services",
    "tcs": "Tata Consultancy Services",
    "infosys": "Infosys",
    "hcltech": "HCLTech",
    "hcl tech": "HCLTech",
    "wipro": "Wipro",
    "icici": "ICICI Bank",
    "bharti airtel": "Bharti Airtel",
    "bharti": "Bharti Airtel",
    "airtel": "Bharti Airtel",
    "state bank of india": "State Bank of India",
    "state bank": "State Bank of India",
    "sbin": "State Bank of India",
    "sbi": "State Bank of India",
    "hindustan unilever": "Hindustan Unilever",
    "hul": "Hindustan Unilever",
    "larsen & toubro": "Larsen & Toubro",
    "larsen": "Larsen & Toubro",
    "bajaj finance": "Bajaj Finance",
    "kotak mahindra bank": "Kotak Mahindra Bank",
    "kotak": "Kotak Mahindra Bank",
    "axis bank": "Axis Bank",
    "maruti suzuki": "Maruti Suzuki",
    "maruti": "Maruti Suzuki",
    "sun pharmaceutical": "Sun Pharmaceutical",
    "sun pharma": "Sun Pharmaceutical",
    "tata motors": "Tata Motors",
    "ntpc": "NTPC",
    "ultratech cement": "UltraTech Cement",
    "ultratech": "UltraTech Cement",
    "mahindra & mahindra": "Mahindra & Mahindra",
    "mahindra and mahindra": "Mahindra & Mahindra",
    "titan company": "Titan Company",
    "titan": "Titan Company",
}
AMOUNT = re.compile(
    r"(?P<metric>gross revenue|operating income|income from operations|cost of revenue|net income|revenue)"
    r"(?: were| was)? [₹$]?(?P<amount>[0-9][0-9,]*(?:\.[0-9]+)?) (?:crore|million)"
    r"(?: for fiscal (?P<fiscal>20[0-9]{2})| in fiscal (?P<in_fiscal>20[0-9]{2})| in (?P<calendar>20[0-9]{2}))?",
    re.I,
)
COMPARISON = re.compile(
    r", compared with [₹$]?(?P<prior>[0-9][0-9,]*(?:\.[0-9]+)?) (?:crore|million) for fiscal (?P<prior_year>20[0-9]{2})",
    re.I,
)
SERIES = re.compile(
    r"[₹$](?P<amount>[0-9][0-9,]*(?:\.[0-9]+)?) (?:crore|million) for fiscal (?P<year>20[0-9]{2})",
    re.I,
)


def _year(match: re.Match) -> Optional[str]:
    return match.group("fiscal") or match.group("in_fiscal") or match.group("calendar")



@dataclass
class SessionState:
    session_id: str
    turns: list[dict] = field(default_factory=list)
    token_estimate: int = 0

    def remember(self, question: str, answer: str) -> None:
        self.turns.append({"question": question, "answer": answer})
        self.turns = self.turns[-8:]


class SessionStore:
    """Session memory, optionally persisted to SQLite so turns survive a restart."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._path = path
        if path:
            import os
            import sqlite3
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, turns TEXT, tokens INTEGER)")

    def get(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = self._load(session_id) or SessionState(session_id)
        return self._sessions[session_id]

    def save(self, state: SessionState) -> None:
        if not self._path:
            return
        import json
        import sqlite3
        with sqlite3.connect(self._path) as db:
            db.execute(
                "INSERT OR REPLACE INTO sessions (id, turns, tokens) VALUES (?, ?, ?)",
                (state.session_id, json.dumps(state.turns), state.token_estimate),
            )

    def _load(self, session_id: str) -> Optional[SessionState]:
        if not self._path:
            return None
        import json
        import sqlite3
        with sqlite3.connect(self._path) as db:
            row = db.execute("SELECT turns, tokens FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return SessionState(session_id, json.loads(row[0]), int(row[1]))


@dataclass
class Plan:
    intent: str
    companies: list[str]
    periods: list[str]
    metric: str
    formula: Optional[str] = None
    refusal_reason: Optional[str] = None
    # Fiscal years the user explicitly asked about; answers must be grounded in exactly these years.
    years: list[str] = field(default_factory=list)


class FinancialCopilot:
    """A bounded planner -> executor -> critic system.

    The deterministic policy layer keeps JSON, arithmetic, citations, and
    refusals reliable when a hosted small model is weak. `model_name` records
    the configured backend; tests use the local fallback.
    """

    MAX_STEPS = 10
    MAX_TOKENS = 6000

    def __init__(self, tools: ToolRegistry, sessions: Optional[SessionStore] = None, model_name: str = "local-policy-fallback"):
        self.tools = tools
        self.sessions = sessions or SessionStore()
        self.model_name = model_name
        self.latest_year = _latest_corpus_year(tools)

    def answer(self, question: str, session_id: str = "default") -> CopilotResponse:
        state = self.sessions.get(session_id)
        if state.token_estimate >= self.MAX_TOKENS:
            return self._response(
                question,
                state,
                "This session has reached its token budget. Start a new session to continue.",
                "refuse",
                [],
                None,
                "low",
                "Token budget exceeded.",
                [],
                time.perf_counter(),
                "token_budget",
            )
        from finsight.graph import invoke_copilot
        return invoke_copilot(self, question, session_id)

    def _plan(self, question: str, turns: Optional[list] = None) -> Plan:
        for pattern, reason in REFUSAL_PATTERNS:
            if pattern.search(question):
                return Plan("refusal", [], [], "", refusal_reason=reason)
        years = _requested_years(question)
        unavailable = [year for year in years if year > self.latest_year]
        if unavailable:
            missing = ", ".join(f"FY{year}" for year in unavailable)
            return Plan(
                "refusal", [], [], "",
                refusal_reason=f"The requested period ({missing}) is unavailable: the corpus only covers filings up to FY{self.latest_year}.",
                years=years,
            )
        lowered = question.lower()
        if any(re.search(rf"\b{name}\b", lowered) for name in OUTSIDE_CORPUS):
            return Plan("refusal", [], [], "", refusal_reason="That company is outside the current NIFTY 50 development corpus.")
        companies = []
        for key, name in COMPANIES.items():
            if re.search(rf"\b{key}\b", lowered) and name not in companies:
                companies.append(name)
        periods = [f"FY{year}" for year in years]
        if "FY2024" in periods and re.search(r"\bq4\b", lowered):
            periods.append("FY2024 Q4")
        if "three-year" in lowered or "three most recent" in lowered:
            periods = ["FY2022", "FY2023", "FY2024", "FY2025"]
        metric = ""
        for candidate in ("operating margin", "gross margin", "operating income", "net sales", "revenue", "risk"):
            if candidate in lowered:
                metric = candidate
                break
        intent = "fact"
        if "compare" in lowered or "higher" in lowered or "which company" in lowered:
            intent = "comparison"
        elif len(companies) >= 2 and " and " in lowered:
            intent = "multi_document"
        elif "margin" in lowered or "growth" in lowered or "by what percent" in lowered:
            intent = "calculation"
        elif "trend" in lowered or "every year" in lowered:
            intent = "trend"
        elif "risk" in lowered or "accounting" in lowered or "which source" in lowered:
            intent = "qualitative"
        formula = None
        if "growth" in lowered or "by what percent" in lowered:
            formula = "(current - prior) / prior * 100"
        elif "gross margin" in lowered:
            formula = "(revenue - cost_of_revenue) / revenue * 100"
        elif "operating margin" in lowered:
            formula = "operating_income / revenue * 100"
        plan = Plan(intent, companies, periods, metric, formula, years=years)
        if turns and not plan.refusal_reason and not plan.companies:
            if re.search(r"\b(it|its|that|those|same|again|there|previous|this company)\b", question, re.I):
                earlier = self._plan(turns[-1]["question"])
                if earlier.companies:
                    plan.companies = earlier.companies
                if not plan.periods and earlier.periods:
                    plan.periods = earlier.periods
                    plan.years = earlier.years
        return plan

    def _search(self, plan: Plan, question: str, calls: list[ToolCallRecord]) -> list[dict]:
        evidence: list[dict] = []
        targets = plan.companies or [None]
        for company in targets:
            arguments = {"query": question, "company": company, "period": None}
            result = self._call_with_retry("report_search", arguments, calls)
            evidence.extend(result.get("evidence", []))
        return evidence

    def _metadata(self, plan: Plan, calls: list[ToolCallRecord]) -> None:
        for company in plan.companies[:2]:
            self._call_with_retry("filing_metadata", {"company": company, "period": plan.periods[0] if plan.periods else None}, calls)

    def _calculate(self, plan: Plan, evidence: list[dict], calls: list[ToolCallRecord]) -> tuple[Optional[str], Union[float, dict, None]]:
        if not plan.formula:
            return None, None
        observations = _observations(evidence)
        try:
            if plan.formula == "(current - prior) / prior * 100" and plan.intent == "comparison" and len(plan.companies) >= 2:
                current_year, prior_year = _growth_years(plan)
                results = {}
                for company in plan.companies:
                    current = _metric(observations, company, current_year, "revenue")
                    prior = _metric(observations, company, prior_year, "revenue")
                    expression = f"({current} - {prior}) / {prior} * 100"
                    result = self._call_with_retry("financial_calculator", {"expression": expression}, calls)
                    results[company] = result.get("value")
                return "(current - prior) / prior * 100", results
            if plan.formula == "(current - prior) / prior * 100":
                current_year, prior_year = _growth_years(plan)
                current = _metric(observations, plan.companies[0], current_year, "revenue")
                prior = _metric(observations, plan.companies[0], prior_year, "revenue")
                expression = f"({current} - {prior}) / {prior} * 100"
                result = self._call_with_retry("financial_calculator", {"expression": expression}, calls)
                return expression, result.get("value")
            if plan.intent == "comparison" and "operating_income" in plan.formula:
                margins = {}
                for company in plan.companies:
                    operating = _metric(observations, company, _target_year(plan), "operating")
                    revenue = _metric(observations, company, _target_year(plan), "revenue")
                    expression = f"{operating} / {revenue} * 100"
                    result = self._call_with_retry("financial_calculator", {"expression": expression}, calls)
                    margins[company] = result.get("value")
                return "operating_income / revenue * 100", margins
            if "cost_of_revenue" in plan.formula:
                revenue = _metric(observations, plan.companies[0], "2025", "revenue")
                cost = _metric(observations, plan.companies[0], "2025", "cost")
                expression = f"({revenue} - {cost}) / {revenue} * 100"
            else:
                year = _target_year(plan)
                operating = _metric(observations, plan.companies[0], year, "operating")
                revenue = _metric(observations, plan.companies[0], year, "revenue")
                expression = f"{operating} / {revenue} * 100"
            result = self._call_with_retry("financial_calculator", {"expression": expression}, calls)
            return expression, result.get("value")
        except (KeyError, IndexError, ZeroDivisionError):
            if plan.metric == "operating margin" and plan.companies:
                stated = _stated_margin(evidence, plan.companies[0], _target_year(plan))
                if stated is not None:
                    return "reported_operating_margin", stated
            return None, None

    def _critic(self, plan: Plan, evidence: list[dict], value: Union[float, dict, None], calculation: Optional[str]) -> tuple[str, str, list[Citation], str, Optional[str]]:
        citations = _citations(evidence)
        if not citations:
            return ("The corpus does not contain enough evidence to answer this question.", "refuse", [], "low", "No supporting filing evidence was retrieved.")
        if calculation == "reported_operating_margin" and isinstance(value, float):
            return (f"The reported operating margin is {value:.1f}%.", "answer", citations, "high", None)
        if plan.intent == "calculation":
            if not isinstance(value, float):
                return ("A required input is missing, so the calculation cannot be completed.", "refuse", citations, "low", "Missing calculation input.")
            return (f"The calculated result is {value:.1f}%. Formula: `{plan.formula}`.", "answer", citations, "high", None)
        if plan.intent == "comparison" and plan.formula and not isinstance(value, dict):
            return ("A required input is missing, so the comparison cannot be completed.", "refuse", citations, "low", "Missing comparison input.")
        if plan.intent == "comparison" and isinstance(value, dict):
            ranked = sorted((item for item in value.items() if isinstance(item[1], float)), key=lambda item: item[1], reverse=True)
            if not ranked:
                return ("The comparison could not be completed from the retrieved evidence.", "refuse", citations, "low", "Missing comparison input.")
            label = "revenue growth" if plan.formula and "current - prior" in plan.formula else "operating margin"
            details = ", ".join(f"{company}: {margin:.1f}%" for company, margin in ranked)
            return (f"{ranked[0][0]} has the higher {label}. {details}.", "answer", citations, "high", None)
        if plan.intent == "trend":
            reported = _revenue_years(plan, evidence)
            missing = [year for year in plan.years if year not in reported]
            if missing:
                return _unavailable(missing)
            return (_trend_answer(plan, evidence), "answer", citations[:3], "high", None)
        if plan.years and plan.intent in {"qualitative", "fact", "multi_document"}:
            supported = [item for item in evidence if all(_reports_year(item, year, plan.metric) for year in plan.years)]
            if not supported:
                return _unavailable(plan.years)
            evidence = supported
            citations = _citations(evidence)
        if plan.intent == "multi_document":
            excerpts = []
            for company in plan.companies:
                rows = [item for item in evidence if item["company"] == company]
                metric_hits = [item for item in rows if plan.metric and plan.metric in item["excerpt"].lower()]
                match = (metric_hits or rows or [None])[0]
                if match:
                    excerpts.append(match["excerpt"])
            if excerpts:
                return (" ".join(excerpts), "answer", citations[:4], "high", None)
        if plan.intent in {"qualitative", "fact", "multi_document"}:
            return (evidence[0]["excerpt"], "answer", citations[:3], "high", None)
        return (evidence[0]["excerpt"], "answer", citations[:3], "medium", None)

    def _call_with_retry(self, name: str, arguments: dict, calls: list[ToolCallRecord]) -> dict:
        result = self.tools.call(name, arguments)
        if result.status == "error":
            calls.append(ToolCallRecord(tool=name, arguments=arguments, status="retried", detail=result.detail))
            repaired = dict(arguments)
            if name == "financial_calculator":
                repaired["expression"] = str(arguments.get("expression", "")).replace(",", "")
            elif "query" in repaired:
                repaired["query"] = str(repaired["query"])[:500]
            result = self.tools.call(name, repaired)
        calls.append(ToolCallRecord(tool=name, arguments=arguments, status=result.status, detail=result.detail))
        if result.status == "error":
            return {}
        return result.payload

    def _response(self, question, state, answer, behavior, citations, calculation, confidence, refusal, calls, started, reason, provider_note_text: str = "") -> CopilotResponse:
        elapsed = (time.perf_counter() - started) * 1000
        tokens = max(1, (len(question) + len(answer)) // 4)
        state.token_estimate += tokens
        state.remember(question, answer)
        self.sessions.save(state)
        from finsight.providers import current_provider
        caveats = ["Figures are normalized to INR crore from official company investor-relations sources; verify consequential analysis against the original annual report."]
        if provider_note_text:
            caveats.append(provider_note_text)
        return CopilotResponse(
            answer=answer,
            behavior=behavior,
            citations=citations,
            calculation=calculation,
            confidence=confidence,
            refusal_reason=refusal,
            caveats=caveats,
            trace_id=str(uuid.uuid4()),
            tool_calls=calls,
            latency_ms=round(elapsed, 3),
            token_estimate=tokens,
            termination_reason=reason,
            provider=current_provider(),
        )


def _grounded_phrase(question: str, answer: str) -> tuple[str, str]:
    """Phrase a completed answer with the course key, and reject any new numbers."""
    from finsight.providers import current_provider
    if current_provider() != "course":
        return answer, ""
    try:
        import json
        from finsight.llm import chat, load_config
        if not load_config().enabled:
            return answer, "Course API key is not configured. Showing the FastAPI answer."
        raw = chat(
            [
                {"role": "system", "content": "Rewrite the answer in one sentence. Do not add numbers or advice. Return JSON with an answer field."},
                {"role": "user", "content": answer},
            ],
            timeout=20,
            max_tokens=256,
            attempts=2,
        )
        candidate = str(json.loads(raw["content"]).get("answer") or "")
        allowed = set(re.findall(r"\d[\d,]*(?:\.\d+)?", answer))
        introduced = set(re.findall(r"\d[\d,]*(?:\.\d+)?", candidate)) - allowed
        if candidate and not introduced:
            return candidate, "Phrased with the course API key."
        return answer, "Course model changed a figure, so the FastAPI answer was kept."
    except Exception:
        return answer, "Course API did not respond. Showing the FastAPI answer."


def _usable(evidence: list[dict]) -> list[dict]:
    return [item for item in evidence if not INSTRUCTION.search(item.get("excerpt", ""))]


def _stated_margin(evidence: list[dict], company: str, year: str) -> Optional[float]:
    """A reported margin, only when the filing states it for the requested fiscal year."""
    for item in evidence:
        if item.get("company") != company:
            continue
        for match in STATED_MARGIN.finditer(item.get("excerpt", "")):
            stated_year = match.group("year") or _period_year(item.get("fiscal_period", ""))
            if stated_year == year:
                return float(match.group("pct"))
    return None


def _requested_years(question: str) -> list[str]:
    years = set()
    for match in YEAR_MENTION.finditer(question):
        fy = match.group("fy")
        if fy:
            years.add(fy if len(fy) == 4 else f"20{fy}")
        else:
            years.add(match.group("year"))
    return sorted(years)


def _latest_corpus_year(tools: ToolRegistry) -> str:
    """Latest fiscal period covered by a filing in the corpus (later periods are unavailable)."""
    chunks = getattr(getattr(tools, "retriever", None), "chunks", None) or []
    years = [_period_year(chunk.passage.fiscal_period) for chunk in chunks]
    return max((year for year in years if year), default=DEFAULT_LATEST_YEAR)


def _period_year(period: str) -> Optional[str]:
    match = re.search(r"20[0-9]{2}", period or "")
    return match.group(0) if match else None


def _reports_year(item: dict, year: str, metric: str) -> bool:
    """True when a sentence of the excerpt states the metric for that fiscal year.

    A bare date ("December 31, 2021") or an unrelated sentence that merely names the
    year ("During fiscal 2019, the company delisted ...") does not count as data for it.
    """
    period = re.compile(rf"\b(?:fiscal(?: year)?|FY)\s*{year}\b", re.I)
    for sentence in re.split(r"(?<=[.;])\s+", item.get("excerpt", "")):
        if period.search(sentence) and (not metric or metric in sentence.lower()):
            return True
    return not metric and _period_year(item.get("fiscal_period", "")) == year


def _revenue_years(plan: Plan, evidence: list[dict]) -> set[str]:
    return {
        item["year"]
        for item in _observations(evidence)
        if item["metric"] == "revenue" and (not plan.companies or item["company"] in plan.companies)
    }


def _unavailable(years: list[str]) -> tuple[str, str, list[Citation], str, Optional[str]]:
    periods = ", ".join(f"FY{year}" for year in years)
    return (
        f"The requested period ({periods}) is unavailable in the retrieved filings, so I cannot answer for it.",
        "refuse",
        [],
        "low",
        f"No filing evidence for {periods} was retrieved.",
    )


def _observations(evidence: list[dict]) -> list[dict]:
    observations = []
    for item in evidence:
        text = item["excerpt"]
        for match in AMOUNT.finditer(text):
            year = _year(match)
            metric = match.group("metric")
            if year and not (metric.lower() == "revenue" and re.search(r"cost of revenue|operating income|income from operations|gross revenue", text[max(0, match.start()-24):match.start()], re.I)):
                observations.append(_observation(item, metric, year, match.group("amount")))
        for match in SERIES.finditer(text):
            prefix = text[max(0, match.start() - 80):match.start()]
            if re.search(r"revenue was|revenue were", prefix, re.I):
                metric = "revenue"
            else:
                continue
            observations.append(_observation(item, metric, match.group("year"), match.group("amount")))
        comparison = COMPARISON.search(text)
        if comparison and observations:
            observations.append(_observation(evidence_item=item, metric=observations[-1]["metric"], year=comparison.group("prior_year"), amount=comparison.group("prior")))
    return observations


def _observation(evidence_item: dict, metric: str, year: str, amount: str) -> dict:
    normalized = metric.lower()
    return {"company": evidence_item["company"], "metric": normalized, "year": year, "value": float(amount.replace(",", ""))}


def _metric(observations: list[dict], company: str, year: str, kind: str) -> float:
    choices = {
        "revenue": ("revenue",),
        "operating": ("operating income", "income from operations"),
        "cost": ("cost of revenue",),
    }[kind]
    for metric in choices:
        for item in observations:
            if item["company"] == company and item["year"] == year and item["metric"] == metric:
                return item["value"]
    raise KeyError((company, year, kind))


def _target_year(plan: Plan) -> str:
    for period in plan.periods:
        match = re.search(r"20[0-9]{2}", period)
        if match:
            return match.group(0)
    return DEFAULT_LATEST_YEAR


def _growth_years(plan: Plan) -> tuple[str, str]:
    years = sorted({match.group(0) for period in plan.periods for match in re.finditer(r"20[0-9]{2}", period)})
    if len(years) >= 2:
        return years[-1], years[-2]
    year = int(_target_year(plan))
    return str(year), str(year - 1)


def _trend_answer(plan: Plan, evidence: list[dict]) -> str:
    observations = [item for item in _observations(evidence) if item["metric"] == "revenue" and (not plan.companies or item["company"] in plan.companies)]
    yearly = {}
    for item in observations:
        yearly.setdefault((item["company"], item["year"]), item["value"])
    if not yearly:
        return evidence[0]["excerpt"]
    ordered = sorted(yearly.items())
    values = [value for _, value in ordered]
    direction = "increased in each consecutive year" if all(later > earlier for earlier, later in zip(values, values[1:])) else "did not increase in every consecutive year"
    series = ", ".join(f"FY{year} ₹{value:,.1f} crore" for (_, year), value in ordered)
    return f"The cited revenue series is {series}. It {direction}."


def _citations(evidence: list[dict]) -> list[Citation]:
    citations = []
    seen = set()
    for item in evidence:
        key = (item["document_id"], item["page"])
        if key in seen:
            continue
        seen.add(key)
        citations.append(Citation(**{field: item[field] for field in Citation.model_fields}))
    return citations
