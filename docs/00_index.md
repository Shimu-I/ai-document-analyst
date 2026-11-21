# 00 - Documentation index and how to use this manual

## What this project is, in two sentences

AI Document Analyst converts PDF, Word, Excel, PowerPoint, CSV, images, data files, HTML and code into clean Markdown, identifies the kind of document, and writes a
short summary. The Markdown is smaller than the original and can be pasted into an AI chat to save tokens, or kept as a plain-text copy.

## Chapters

| # | Chapter | Answers |
|---|---|---|
| 01 | [Project brief](01_project_brief.md) | What is built, for whom, what is out of scope |
| 02 | [Conversion notes](02_conversion_notes.md) | What each converter keeps, drops and warns about |
| 03 | [Evaluation](03_evaluation.md) | Measured quality, comparison with markitdown, caveats |
| 04 | [Concepts and architecture](04_concepts_and_architecture.md) | How it works, with diagrams |
| 05 | [Build from scratch](05_build_from_scratch.md) | Rebuilding the project phase by phase, with checks and commit messages |
| 06 | [User manual](06_user_manual.md) | Installing and using the web page, command line and API |
| 07 | [Free setup](07_free_setup.md) | Optional free AI summary, OCR languages, other systems |
| 08 | [Testing and reproduction](08_testing_and_reproduction.md) | Running tests and repeating every number |
| 09 | [Free deployment](09_deployment_free.md) | Hosting options at no cost, security checklist |
| 10 | [Corner cases and troubleshooting](10_corner_cases_and_troubleshooting.md) | 49 awkward inputs, limits, fixes by symptom |
| 11 | [FAQ and interview questions](11_faq_and_interview_questions.md) | Practical questions and presentation questions |
| - | [Figures](assets/README.md) | How each image is regenerated |

## Reading paths

| Goal | Path |
|---|---|
| Run it today | 06 section 1 and 2, then 10 section 3 if something breaks |
| Understand how it works | 04, then 02, then read `src/convert/base.py` and `src/service.py` |
| Learn by rebuilding it | 04, then 05 phase by phase (type the code, run the check, commit), then 08 |
| Present it or answer questions | README, PORTFOLIO, 03, 11 |
| Put a demo online | 09, then the checklist at its end |

## How to learn from this manual instead of copying it

1. Read 04 once without a keyboard. The goal is to be able to redraw the architecture figure from memory.
2. In 05, finish each phase in an empty folder: write the code from the description, run the "Check", then try the "Try to break it" items. A failing check is the useful part.
3. Compare the result with the repository version only after the check passes, and note each difference with the reason.
4. Commit after each phase with the suggested message. The history then shows the learning path.
5. Finish with 08 and 10: repeat the numbers and find one new corner case that is not in the table.

## Conventions

Commands start from the project root with the virtual environment active. `python` inside the environment equals `python3` outside it. Paths are relative to the project root.
Figures state their data source. Where something was not run (Streamlit page, API server, Docker, hosting, Windows, macOS), the text says so.
