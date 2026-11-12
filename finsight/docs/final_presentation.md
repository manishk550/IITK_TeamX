# FinSight final presentation

The deck to present is `docs/FinSight_Final_Presentation.pptx` (12 slides, 16:9).
Rebuild it after a new eval or baseline run:

```bash
PYTHONPATH=src:.vendor python3 scripts/build_deck.py
```

Every figure on the slides is read from `reports/` and `data/` at build time.
Speaker notes are on each slide. Fill in the team name and six members on slide 1 before presenting.

| Slide | Say this |
|---|---|
| 1 Title | Name the team. FinSight answers questions about 20 NIFTY companies on Qwen3-8B, cites the page, and refuses when it should. |
| 2 Problem | A fluent model is not an auditable one. The number has to come from a filing or from the calculator. |
| 3 Contract | 82 questions were frozen first. Checksum is on the slide. Do not say the set was written to fit the score. |
| 4 Architecture | One agent, three stages. LangGraph orders them. Three tools own the facts. |
| 5 Corpus | 1,314 passages across 20 NIFTY companies. Say plainly that 15 companies and HCLTech are cards only, because only four annual-report PDFs were extracted. |
| 6 Baseline | 0% is the earlier free model with no documents, 51 of 82. Say that Qwen3-8B is the configured course model and is not in this table. |
| 7 Retrieval | Recall of the source page, measured apart from answer quality. Production setting is hybrid. |
| 8 Controls | Tool failure, bad JSON, a 10-step cap, a token budget, and session state kept in SQLite. |
| 9 Results | 82 of 82 on the default path, which does not call the hosted model. Do not call this an 8B score. |
| 10 Responsible AI | 24 of 24 adversarial prompts inside policy, including a planted “buy Reliance” passage. |
| 11 Demo | Five questions, then open `/traces`. Stop there. |
| 12 Close | The model is Qwen3-8B and is used for language. The filing is for the number. The 0% table is the earlier model. Then take questions. |
