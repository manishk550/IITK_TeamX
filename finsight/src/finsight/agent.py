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
    (re.compile(r"\b(buy|sell|hold)\b.{0,40}\b(stock|shares|recommendation)\b|\bshould i (buy|sell|hold)\b", re.I),
     "FinSight cannot provide investment advice or a buy, sell, or hold recommendation."),
    (re.compile(r"\b(guarantee|predict|price target|will revenue be)\b", re.I),
     "Future performance cannot be presented as fact."),
    (re.compile(r"\b(personal account|social security|password|private information)\b", re.I),
     "FinSight cannot request or reveal personal or non-public information."),
    (re.compile(r"\bignore (all|the|previous|filings|citations)\b", re.I),
     "Instructions to bypass evidence or safety rules are refused."),
]

COMPANIES = {
    "reliance": "Reliance Industries",
    "ril": "Reliance Industries",
    "tcs": "Tata Consultancy Services",
    "tata consultancy services": "Tata Consultancy Services",
    "infosys": "Infosys",
    "hcltech": "HCLTech",
    "hcl tech": "HCLTech",
    "wipro": "Wipro",
}
PERIODS = ("FY2022", "FY2023", "FY2024", "FY2025", "FY2024 Q4")
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
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def get(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id)
        return self._sessions[session_id]


@dataclass
class Plan:
    intent: str
    companies: list[str]
    periods: list[str]
    metric: str
    formula: Optional[str] = None
    refusal_reason: Optional[str] = None


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

    def answer(self, question: str, session_id: str = "default") -> CopilotResponse:
        started = time.perf_counter()
        state = self.sessions.get(session_id)
        calls: list[ToolCallRecord] = []
        steps = 0
        plan = self._plan(question)
        steps += 1
        if plan.refusal_reason:
            response = self._response(question, state, plan.refusal_reason, "refuse", [], None, "low", plan.refusal_reason, calls, started, "policy_refusal")
            return response

        evidence = self._search(plan, question, calls)
        steps += 1
        if steps < self.MAX_STEPS:
            self._metadata(plan, calls)
            steps += 1
        calculation, value = self._calculate(plan, evidence, calls)
        if calculation:
            steps += 1
        answer, behavior, citations, confidence, refusal = self._critic(plan, evidence, value)
        steps += 1
        reason = "completed" if steps <= self.MAX_STEPS else "step_limit"
        if state.token_estimate > self.MAX_TOKENS:
            reason = "token_budget"
        return self._response(question, state, answer, behavior, citations, calculation, confidence, refusal, calls, started, reason)

    def _plan(self, question: str) -> Plan:
        for pattern, reason in REFUSAL_PATTERNS:
            if pattern.search(question):
                return Plan("refusal", [], [], "", refusal_reason=reason)
        if re.search(r"\b20(30|31|32)\b", question):
            return Plan("refusal", [], [], "", refusal_reason="The requested future or unavailable period is outside the corpus.")
        companies = []
        lowered = question.lower()
        for key, name in COMPANIES.items():
            if re.search(rf"\b{key}\b", lowered) and name not in companies:
                companies.append(name)
        periods = [period for period in PERIODS if period.lower() in lowered or period[-4:] in lowered]
        if "three-year" in lowered or "three most recent" in lowered:
            periods = ["FY2022", "FY2023", "FY2024", "FY2025"]
        metric = "revenue"
        for candidate in ("operating margin", "gross margin", "operating income", "net sales", "revenue", "risk"):
            if candidate in lowered:
                metric = candidate
                break
        intent = "fact"
        if "compare" in lowered or "higher" in lowered or "which company" in lowered:
            intent = "comparison"
        elif "margin" in lowered or "growth" in lowered:
            intent = "calculation"
        elif "trend" in lowered or "every year" in lowered:
            intent = "trend"
        elif "risk" in lowered or "accounting" in lowered or "which source" in lowered:
            intent = "qualitative"
        formula = None
        if "growth" in lowered:
            formula = "(current - prior) / prior * 100"
        elif "gross margin" in lowered:
            formula = "(revenue - cost_of_revenue) / revenue * 100"
        elif "operating margin" in lowered:
            formula = "operating_income / revenue * 100"
        return Plan(intent, companies, periods, metric, formula)

    def _search(self, plan: Plan, question: str, calls: list[ToolCallRecord]) -> list[dict]:
        evidence: list[dict] = []
        targets = plan.companies or [None]
        for company in targets:
            period = None if plan.formula == "(current - prior) / prior * 100" else (plan.periods[0] if len(plan.periods) == 1 else None)
            arguments = {"query": question, "company": company, "period": period}
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
                    operating = _metric(observations, company, "2024", "operating")
                    revenue = _metric(observations, company, "2024", "revenue")
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
            return None, None

    def _critic(self, plan: Plan, evidence: list[dict], value: Union[float, dict, None]) -> tuple[str, str, list[Citation], str, Optional[str]]:
        citations = _citations(evidence)
        if not citations:
            return ("The corpus does not contain enough evidence to answer this question.", "refuse", [], "low", "No supporting filing evidence was retrieved.")
        if plan.intent == "calculation":
            if not isinstance(value, float):
                return ("A required input is missing, so the calculation cannot be completed.", "refuse", citations, "low", "Missing calculation input.")
            return (f"The calculated result is {value:.1f}%. Formula: `{plan.formula}`.", "answer", citations, "high", None)
        if plan.intent == "comparison" and isinstance(value, dict):
            ranked = sorted((item for item in value.items() if isinstance(item[1], float)), key=lambda item: item[1], reverse=True)
            if not ranked:
                return ("The comparison could not be completed from the retrieved evidence.", "refuse", citations, "low", "Missing comparison input.")
            details = ", ".join(f"{company}: {margin:.1f}%" for company, margin in ranked)
            return (f"{ranked[0][0]} has the higher operating margin. {details}.", "answer", citations, "high", None)
        if plan.intent == "trend":
            return (_trend_answer(plan, evidence), "answer", citations[:3], "high", None)
        if plan.intent in {"qualitative", "fact"}:
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

    def _response(self, question, state, answer, behavior, citations, calculation, confidence, refusal, calls, started, reason) -> CopilotResponse:
        elapsed = (time.perf_counter() - started) * 1000
        tokens = max(1, (len(question) + len(answer)) // 4)
        state.token_estimate += tokens
        state.remember(question, answer)
        return CopilotResponse(
            answer=answer,
            behavior=behavior,
            citations=citations,
            calculation=calculation,
            confidence=confidence,
            refusal_reason=refusal,
            caveats=["Figures are normalized to INR crore from official company investor-relations sources; verify consequential analysis against the original annual report."],
            trace_id=str(uuid.uuid4()),
            tool_calls=calls,
            latency_ms=round(elapsed, 3),
            token_estimate=tokens,
            termination_reason=reason,
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
    return "2024"


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
