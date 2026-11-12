from __future__ import annotations
from typing import Optional

"""Strictly validated tools exposed to the agent."""


import ast
import operator
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from finsight.retrieval import HybridRetriever
from finsight.schemas import Evidence


class SearchArgs(BaseModel):
    query: str = Field(min_length=2)
    company: Optional[str] = None
    period: Optional[str] = None


class MetadataArgs(BaseModel):
    company: str = Field(min_length=2)
    period: Optional[str] = None


class CalculatorArgs(BaseModel):
    expression: str = Field(min_length=1, max_length=200)


@dataclass
class ToolResult:
    status: str
    payload: dict
    detail: str = ""


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def safe_calculate(expression: str) -> float:
    """Evaluate arithmetic without allowing names, calls, or power expressions."""
    tree = ast.parse(expression, mode="eval")

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            right = visit(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise ZeroDivisionError("division by zero")
            return _OPS[type(node.op)](visit(node.left), right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](visit(node.operand))
        raise ValueError("unsupported expression")

    return visit(tree)


class ToolRegistry:
    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever

    def call(self, name: str, arguments: dict) -> ToolResult:
        try:
            if name == "report_search":
                args = SearchArgs.model_validate(arguments)
                evidence = self.retriever.search(args.query, company=args.company, period=args.period)
                return ToolResult("ok", {"evidence": [item.model_dump() for item in evidence]})
            if name == "filing_metadata":
                args = MetadataArgs.model_validate(arguments)
                evidence = self.retriever.search(args.company, k=8, company=args.company, period=args.period)
                documents = _documents(evidence)
                if not documents:
                    return ToolResult("error", {}, "no filing metadata found")
                return ToolResult("ok", {"documents": documents})
            if name == "financial_calculator":
                args = CalculatorArgs.model_validate(arguments)
                expression = _normalize_expression(args.expression)
                value = safe_calculate(expression)
                return ToolResult("ok", {"expression": expression, "value": round(value, 6)})
            return ToolResult("error", {}, f"unknown tool: {name}")
        except (ValidationError, ValueError, ZeroDivisionError, SyntaxError) as exc:
            return ToolResult("error", {}, str(exc))


def _documents(evidence: list[Evidence]) -> list[dict]:
    seen: set[str] = set()
    documents = []
    for item in evidence:
        if item.document_id in seen:
            continue
        seen.add(item.document_id)
        documents.append({
            "document_id": item.document_id,
            "company": item.company,
            "fiscal_period": item.fiscal_period,
            "page": item.page,
            "section": item.section,
            "currency": "INR",
            "scale": "crore",
        })
    return documents


def _normalize_expression(expression: str) -> str:
    cleaned = expression.replace(",", "").replace("%", "")
    if not re.fullmatch(r"[0-9+\-*/().\s]+", cleaned):
        raise ValueError("expression contains unsupported characters")
    return cleaned
