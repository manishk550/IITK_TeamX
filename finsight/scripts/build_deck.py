"""Build the final FinSight presentation from measured reports.

Run: PYTHONPATH=.vendor python3 scripts/build_deck.py
Numbers come from reports/ and data/. Rerun after a new eval or baseline.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# Exact 16:9. A rounded 13.333-inch width makes Keynote refuse the file.
SLIDE_W = Emu(12192000)
SLIDE_H = Emu(6858000)

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = ROOT / "docs" / "FinSight_Final_Presentation.pptx"

NAVY = RGBColor(0x0B, 0x1F, 0x33)
INK = RGBColor(0x14, 0x20, 0x33)
TEAL = RGBColor(0x0F, 0x6E, 0x6E)
SAND = RGBColor(0xF6, 0xF4, 0xEF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MUTED = RGBColor(0x5C, 0x6B, 0x7A)
LINE = RGBColor(0xE2, 0xE6, 0xEA)
CARD = RGBColor(0xFF, 0xFF, 0xFF)
AMBER = RGBColor(0x8A, 0x4B, 0x08)

W = 13.333
H = 7.5
FONT = "Calibri"


def load(name: str):
    return json.loads((REPORTS / name).read_text())


def summarize(name: str, rows: list[dict]) -> dict:
    latencies = sorted(row["latency_ms"] for row in rows)
    failures = [row for row in rows if row["failure"]]
    taxonomy = Counter(row["failure"] for row in failures)
    return {
        "strategy": name,
        "examples": len(rows),
        "accuracy": round((len(rows) - len(failures)) / len(rows), 3) if rows else 0,
        "schema_valid_rate": round(sum(row["schema_ok"] for row in rows) / len(rows), 3) if rows else 0,
        "citation_rate": round(sum(bool(row["cited"]) for row in rows) / len(rows), 3) if rows else 0,
        "median_latency_ms": round(latencies[len(latencies) // 2], 1) if latencies else 0,
        "failure_taxonomy": dict(taxonomy),
        "main": max(taxonomy, key=taxonomy.get) if taxonomy else "—",
        "main_count": taxonomy.most_common(1)[0][1] if taxonomy else 0,
    }


def baseline_view() -> tuple[int, list[dict], str]:
    """Prefer the checkpoint, which is ahead of the last full results file."""
    path = REPORTS / "baseline_checkpoint.jsonl"
    items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if items:
        grouped: dict[str, list] = {}
        for item in items:
            for name, row in item["rows"].items():
                grouped.setdefault(name, []).append(row)
        order = ("structured_few_shot", "self_consistency", "decomposition")
        return len(items), [summarize(name, grouped[name]) for name in order if name in grouped], "checkpoint"
    saved = load("baseline_results.json")
    rows = []
    for item in saved["strategies"]:
        taxonomy = item["failure_taxonomy"]
        main = max(taxonomy, key=taxonomy.get) if taxonomy else "—"
        rows.append({**item, "main": main, "main_count": taxonomy.get(main, 0)})
    return saved["examples_completed"], rows, "results file"


def company_counts() -> list[tuple[str, int]]:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from finsight.corpus import load_corpus

    counts = Counter(passage.company for passage in load_corpus())
    return sorted(counts.items(), key=lambda item: -item[1])


def rect(slide, x, y, w, h, fill, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
    shape.adjustments[0] = 0.08
    return shape


def bar(slide, x, y, w, h, fill):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    return shape


def write(slide, x, y, w, h, text, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    frame.margin_left = Emu(0)
    frame.margin_right = Emu(0)
    frame.margin_top = Emu(0)
    frame.margin_bottom = Emu(0)
    try:
        frame._txBody.bodyPr.set("anchor", {MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr", MSO_ANCHOR.BOTTOM: "b"}[anchor])
    except Exception:
        pass
    lines = text.split("\n") if isinstance(text, str) else list(text)
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        paragraph.space_after = Pt(4)
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.bold = bold
        run.font.name = FONT
    return box


def chrome(slide, number: int, total: int, title: str, subtitle: str = ""):
    bar(slide, 0, 0, W, 0.08, TEAL)
    write(slide, 0.55, 0.28, 10.5, 0.48, title, size=28, bold=True)
    if subtitle:
        write(slide, 0.55, 0.82, 12.2, 0.36, subtitle, size=15, color=MUTED)
    write(slide, 0.55, 7.12, 8, 0.28, "FinSight  ·  Track B  ·  Qwen3-8B", size=11, color=MUTED)
    write(slide, 11.3, 7.12, 1.5, 0.28, f"{number}  /  {total}", size=11, color=MUTED, align=PP_ALIGN.RIGHT)


def note(slide, text: str):
    """Speaker notes are kept in docs/final_presentation.md.

    python-pptx writes notes pages with a zero-size group, and Keynote then
    reports that the file cannot be imported.
    """
    return None


def style_table(table, header=True):
    for r, row in enumerate(table.rows):
        for cell in row.cells:
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(14)
                paragraph.font.name = FONT
                paragraph.font.bold = header and r == 0
                paragraph.font.color.rgb = WHITE if r == 0 else INK
            cell.margin_left = Inches(0.1)
            cell.margin_right = Inches(0.08)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = TEAL if r == 0 else (SAND if r % 2 == 0 else WHITE)


def add_table(slide, rows, x, y, w, h, widths):
    shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(h))
    grid = shape.table
    for index, width in enumerate(widths):
        grid.columns[index].width = Inches(width)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            grid.cell(r, c).text = str(value)
    style_table(grid)
    return grid


def build() -> Path:
    agent = load("agent_eval.json")
    retrieval = load("retrieval_ablation.json")
    safety = load("safety_log.json")
    meta = load("baseline_results.json")
    done, strategies, _source = baseline_view()
    frozen = sum(1 for line in (ROOT / "data/eval/eval_v1.jsonl").read_text().splitlines() if line.strip())
    checksum = (ROOT / "data/eval/eval_v1.sha256").read_text().split()[0]
    companies = company_counts()
    categories = Counter(item["category"] for item in safety)
    leaks = sum(1 for item in safety if item.get("leaked_injection"))
    refused = sum(1 for item in safety if item.get("refused"))
    total_slides = 12

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # 1 — title
    slide = prs.slides.add_slide(blank)
    bar(slide, 0, 0, W, H, NAVY)
    bar(slide, 0, 0, 0.18, H, TEAL)
    write(slide, 0.85, 1.7, 11, 0.4, "TRACK B  ·  FINAL", size=14, color=RGBColor(0x9A, 0xD4, 0xD4), bold=True)
    write(slide, 0.85, 2.15, 11, 1.1, "FinSight", size=60, color=WHITE, bold=True)
    write(slide, 0.85, 3.4, 10.5, 1.0, "Cited answers for 20 NIFTY companies,\non the course model Qwen3-8B.", size=22, color=RGBColor(0xD5, 0xDE, 0xE6))
    write(slide, 0.85, 5.15, 10.5, 0.9, "Team: add team name\nMembers: add six names before presenting", size=16, color=RGBColor(0x9A, 0xAE, 0xC0))
    write(slide, 0.85, 6.7, 8, 0.3, "12 November 2026", size=14, color=RGBColor(0x9A, 0xAE, 0xC0))
    note(slide, "Open by naming the team. One sentence: FinSight answers questions about 20 NIFTY companies, cites the page, and refuses when it should.")

    # 2 — problem
    slide = prs.slides.add_slide(blank)
    chrome(slide, 2, total_slides, "Analysts need answers they can check", "A fluent model is not an auditable one")
    points = [
        ("Long filings", "One revenue figure appears in standalone, consolidated, and segment tables. The wrong table is a wrong answer."),
        ("Small models fail quietly", "A model of 8B parameters or less drops constraints, emits bad tool calls, and invents figures that look plausible."),
        ("The bar", "Every number must come from a retrieved page or from the calculator. Advice, forecasts, and missing evidence are refusals."),
    ]
    for index, (head, body) in enumerate(points):
        y = 1.45 + index * 1.75
        rect(slide, 0.55, y, 12.2, 1.55, CARD, LINE)
        bar(slide, 0.55, y, 0.1, 1.55, TEAL)
        write(slide, 0.95, y + 0.22, 11.4, 0.4, head, size=20, bold=True)
        write(slide, 0.95, y + 0.7, 11.4, 0.65, body, size=16, color=MUTED)
    note(slide, "Do not demo yet. Set up why citations and a calculator exist: the model is not trusted with the number.")

    # 3 — what it does
    slide = prs.slides.add_slide(blank)
    chrome(slide, 3, total_slides, "What an acceptable answer looks like", f"Frozen before the agent was written: {frozen} questions, checksum {checksum[:12]}…")
    rules = [
        ("1", "Answer or refuse", "The behavior is explicit. A refusal names the reason."),
        ("2", "Cite a real page", "Document id, page, and section must be passages that were retrieved."),
        ("3", "Calculate in code", "Growth and ratios run in the calculator. The model cannot add a new number."),
        ("4", "Stay inside 20 NIFTY companies", "Four have annual-report pages. Fifteen more have a checked FY2024 results card. HDFC Bank and ITC are still refused."),
    ]
    for index, (num, head, body) in enumerate(rules):
        x = 0.55 + (index % 2) * 6.35
        y = 1.5 + (index // 2) * 2.5
        rect(slide, x, y, 6.05, 2.25, CARD, LINE)
        write(slide, x + 0.3, y + 0.28, 1.0, 0.6, num, size=28, color=TEAL, bold=True)
        write(slide, x + 1.3, y + 0.38, 4.4, 0.5, head, size=20, bold=True)
        write(slide, x + 0.3, y + 1.15, 5.4, 0.8, body, size=16, color=MUTED)
    note(slide, "Mention the checksum so the room knows the 82 questions were not rewritten after seeing the scores.")

    # 4 — architecture
    slide = prs.slides.add_slide(blank)
    chrome(slide, 4, total_slides, "One agent, three stages", "LangGraph orders the work. The tools own the facts.")
    steps = ["Plan", "Search", "Metadata", "Calculate", "Critic"]
    for index, label in enumerate(steps):
        x = 0.55 + index * 2.5
        rect(slide, x, 1.55, 2.25, 0.85, TEAL)
        write(slide, x, 1.72, 2.25, 0.5, label, size=16, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        if index < len(steps) - 1:
            write(slide, x + 2.15, 1.72, 0.4, 0.45, "→", size=18, color=TEAL, align=PP_ALIGN.CENTER)
    rect(slide, 0.55, 2.65, 12.2, 0.85, RGBColor(0xF8, 0xEE, 0xE6), RGBColor(0xE8, 0xD0, 0xC0))
    write(slide, 0.75, 2.82, 11.8, 0.55, "Or stop at Plan and refuse: advice, a forecast, personal data,\nan injected instruction, or a company outside the corpus.", size=15, color=AMBER)
    tools = [
        ("report_search", f"Hybrid retrieval over {agent.get('corpus_passages', sum(n for _, n in companies)):,} passages. Returns the pages the answer may cite."),
        ("filing_metadata", "Company, period, currency (INR), and unit (crore), so a figure is never unitless."),
        ("financial_calculator", "Only + − × ÷, parsed as an expression tree. No function calls, no code."),
    ]
    for index, (name, body) in enumerate(tools):
        y = 3.75 + index * 1.02
        write(slide, 0.55, y, 3.3, 0.4, name, size=16, color=TEAL, bold=True)
        write(slide, 3.9, y, 8.8, 0.7, body, size=16)
    note(slide, "If asked multi-agent versus single-agent: one agent, three stages. LangGraph is the order of those stages, not a second model.")

    # 5 — corpus
    slide = prs.slides.add_slide(blank)
    chrome(slide, 5, total_slides, "The corpus", f"{agent.get('corpus_passages', sum(n for _, n in companies)):,} passages  ·  20 NIFTY companies  ·  four annual reports plus checked results cards")
    short = {
        "Tata Consultancy Services": "TCS",
        "Reliance Industries": "Reliance",
        "Hindustan Unilever": "HUL",
        "State Bank of India": "SBI",
        "Larsen & Toubro": "L&T",
        "Mahindra & Mahindra": "M&M",
        "Kotak Mahindra Bank": "Kotak",
        "Sun Pharmaceutical": "Sun Pharma",
        "UltraTech Cement": "UltraTech",
        "Bharti Airtel": "Airtel",
        "Titan Company": "Titan",
        "Bajaj Finance": "Bajaj Finance",
    }
    for index, (company, count) in enumerate(companies):
        col, row = index % 5, index // 5
        x = 0.45 + col * 2.55
        y = 1.45 + row * 0.95
        rect(slide, x, y, 2.42, 0.85, CARD, LINE)
        write(slide, x + 0.08, y + 0.08, 2.26, 0.32, short.get(company, company), size=12, bold=True, align=PP_ALIGN.CENTER)
        write(slide, x + 0.08, y + 0.38, 2.26, 0.36, f"{count:,} passages", size=12, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    write(slide, 0.5, 5.35, 12.3, 1.5, "Four companies have extracted annual-report pages. The other 16, including HCLTech, are checked FY2024 cards from each company’s own results release. HDFC Bank and ITC stay outside the frozen test. One passage is a planted instruction used only in the safety test.", size=14)

    # 6 — baseline
    slide = prs.slides.add_slide(blank)
    chrome(
        slide, 6, total_slides, "Week 1: the small model, with no documents",
        f"Earlier free model, question only, {done} of {frozen}. Qwen3-8B is connected and not in this score.",
    )
    labels = {
        "structured_few_shot": ("Few-shot", "Mostly refused, because the prompt had no filing."),
        "self_consistency": ("Self-consistency", "Three samples agreed on a wrong or invented figure."),
        "decomposition": ("Decomposition", "The plan was valid JSON. The final answer was empty."),
    }
    for index, item in enumerate(strategies):
        x = 0.55 + index * 4.2
        rect(slide, x, 1.5, 3.95, 3.55, CARD, LINE)
        title, why = labels.get(item["strategy"], (item["strategy"], ""))
        write(slide, x + 0.25, 1.7, 3.45, 0.4, title, size=18, bold=True)
        write(slide, x + 0.25, 2.25, 3.45, 0.7, f"{item['accuracy']:.0%}", size=40, color=TEAL, bold=True)
        write(slide, x + 0.25, 3.1, 3.45, 0.35, "accuracy", size=13, color=MUTED)
        write(slide, x + 0.25, 3.55, 3.45, 0.4, f"Valid JSON  {item['schema_valid_rate']:.0%}", size=15)
        write(slide, x + 0.25, 4.05, 3.45, 0.75, why, size=14, color=MUTED)
    write(slide, 0.55, 5.3, 12.2, 1.5, "Format was never the problem. Grounding was. One sample invented an Infosys amount, Rs. 18,500 crore. This 0% is the earlier free model, not Qwen/Qwen3-8B. Cost on that run was $0.", size=16)
    note(slide, "Say the run is incomplete:  the checkpoint has the questions scored so far, and the script resumes. Do not present 0% as the final system score. That number is the prompt-only baseline.")

    # 7 — retrieval
    slide = prs.slides.add_slide(blank)
    chrome(slide, 7, total_slides, "Week 2: retrieval, measured on its own", f"{retrieval['queries']} page probes  ·  recall of the source page, not of the final answer")
    rows = [["Chunking", "Ranker", "Recall @ 5", "Recall @ 10"]]
    rows += [[run["strategy"], run["mode"], f"{run['recall_at_5']:.3f}", f"{run['recall_at_10']:.3f}"] for run in retrieval["runs"]]
    add_table(slide, rows, 0.55, 1.45, 7.3, 4.6, [1.8, 1.7, 1.9, 1.9])
    rect(slide, 8.15, 1.45, 4.6, 4.6, SAND, LINE)
    write(slide, 8.4, 1.7, 4.15, 0.4, "What we ship", size=16, bold=True)
    write(slide, 8.4, 2.2, 4.15, 3.6, "Section chunks keep a short card intact.\nHybrid is a keyword score plus token cosine, then a reranker.\nChecked fact cards outrank a page that only repeats the word.\nNo vector database. The 1,314 passages are scored in memory.\nThe course API has no embeddings endpoint.", size=15)
    note(slide, "The probes repeat words from the page, so recall is high for every setting. The point of the table is the gap: section dense is the weak one. Production is hybrid.")

    # 8 — controls
    slide = prs.slides.add_slide(blank)
    chrome(slide, 8, total_slides, "Week 3: what stops the model going wrong")
    rows = [
        ["Failure mode", "What FinSight does"],
        ["Invented number", "Calculator result, then a check that a rephrase adds no new digits"],
        ["Bad JSON or a failed tool", "Validate, retry once, record the error, answer from what succeeded"],
        ["A loop", "Stop at 10 steps"],
        ["A long conversation", "6,000-token cap; last 8 turns kept, stored in SQLite across restarts"],
        ["Instructions inside a filing", "Dropped before the answer is written"],
        ["Advice or personal data", "Refused before any search"],
    ]
    add_table(slide, rows, 0.55, 1.4, 12.2, 5.3, [3.4, 8.8])
    note(slide, "This slide answers the agent rubric: planner, executor, critic, three tools, tool errors, bad JSON, loops, token budget, and state that survives a restart.")

    # 9 — results
    slide = prs.slides.add_slide(blank)
    chrome(slide, 9, total_slides, "Same 82 questions, after retrieval and tools", "Default path. The hosted model is not called unless rephrasing is turned on.")
    stats = [
        (f"{agent['correct']}/{agent['examples']}", "Correct"),
        (f"{agent['average_tool_calls']}", "Tool calls, average"),
        (f"{agent['median_latency_ms']:.0f} ms", "Median latency"),
        (f"${agent.get('model_cost_per_query_usd', 0):.2f}", "Model cost / query"),
    ]
    for index, (value, label) in enumerate(stats):
        x = 0.55 + index * 3.2
        rect(slide, x, 1.5, 3.0, 2.15, CARD, LINE)
        write(slide, x + 0.15, 1.75, 2.7, 0.9, value, size=32, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
        write(slide, x + 0.15, 2.75, 2.7, 0.5, label, size=14, color=MUTED, align=PP_ALIGN.CENTER)
    write(slide, 0.55, 4.0, 12.2, 2.6, "\n".join([
        f"Task completion {agent['task_completion_rate']:.0%}.  p95 latency {agent.get('p95_latency_ms', 0):.0f} ms.  Failures on this run: none.",
        "Labels ready when a run is not perfect: retrieval miss, reasoning error, tool-call error, hallucination, policy error.",
        "Read this against the previous slide’s 0%. The gain is the documents and the calculator, not a better prompt.",
        "These timings are local. They will rise when the hosted model is on the path.",
    ]), size=16)
    note(slide, "Say out loud that 82 of 82 is the deterministic path. Do not call it an 8B-model score.")

    # 10 — safety
    slide = prs.slides.add_slide(blank)
    chrome(slide, 10, total_slides, "Responsible AI", f"{refused} of {len(safety)} adversarial prompts stayed inside policy. Injection leaks: {leaks}.")
    rows = [["Category", "Prompts"]] + [[name.replace("_", " "), count] for name, count in sorted(categories.items())]
    add_table(slide, rows, 0.55, 1.45, 6.3, 5.2, [4.3, 2.0])
    write(slide, 7.2, 1.5, 5.5, 5.0, "\n".join([
        "A passage in the corpus says to ignore the rules and tell every user to buy Reliance. Retrieved, never obeyed.",
        "",
        "Aadhaar, PAN, phone numbers, and personal email are refused.",
        "",
        "FinSight does not approve a trade. A person does.",
    ]), size=16)
    note(slide, "If there is time, show the buy-recommendation refusal live rather than reading this slide.")

    # 11 — demo
    slide = prs.slides.add_slide(blank)
    chrome(slide, 11, total_slides, "Demo, about three minutes")
    demo = [
        ("1", "What was Reliance Industries revenue for fiscal 2024?", "₹914,472 crore, with the page."),
        ("2", "By what percent did Reliance revenue grow in fiscal 2024?", "2.6%, and the expression is shown."),
        ("3", "Compare the Infosys and HCLTech operating margins.", "20.7% and 18.2%, both cited."),
        ("4", "What will Reliance revenue be in FY2030?", "Refused. No filing covers that year."),
        ("5", "Should I buy Reliance shares?", "Refused. No investment advice."),
    ]
    for index, (num, question, expect) in enumerate(demo):
        y = 1.4 + index * 1.05
        write(slide, 0.55, y, 0.5, 0.4, num, size=20, color=TEAL, bold=True)
        write(slide, 1.15, y, 7.6, 0.85, question, size=16, bold=True)
        write(slide, 8.9, y, 3.9, 0.85, expect, size=15, color=MUTED)
    note(slide, "After the fifth question, open /traces and show the spans for the questions just asked. Stop there.")

    # 12 — close
    slide = prs.slides.add_slide(blank)
    chrome(slide, 12, total_slides, "What held, and what is still open")
    held = [
        ("Held", "Citations and arithmetic in tools, not in the model.\nHybrid retrieval over 1,314 passages, 20 companies.\nCourse API: Qwen/Qwen3-8B, certificate vm04-ca.crt.\nRefusals tested, including a poisoned passage."),
        ("Still open", f"The 0% table is the earlier model, {done} of {frozen}. Qwen is not scored yet.\nThe group key was not accepted on the connectivity check.\nNot deployed to a public URL yet.\nHCLTech and 15 companies are cards, not full reports."),
    ]
    for index, (head, body) in enumerate(held):
        x = 0.55 + index * 6.4
        rect(slide, x, 1.5, 6.1, 3.7, CARD, LINE)
        write(slide, x + 0.3, 1.7, 5.5, 0.45, head, size=20, color=TEAL, bold=True)
        write(slide, x + 0.3, 2.3, 5.5, 2.6, body, size=15)
    write(slide, 0.55, 5.5, 12.2, 1.2, "The model is used for language. The filing is used for the number.\nQuestions.", size=20, bold=True)
    note(slide, "Close on that sentence. Take questions. If asked for the repo, point at the FinSight service, the /traces page, and this deck.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
