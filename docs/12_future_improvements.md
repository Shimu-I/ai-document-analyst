# 12 - Future Improvements

Ideas ordered by value for the effort. Each one removes a limit from [11](11_limitations_and_known_issues.md).

```mermaid
quadrantChart
    title Value against effort
    x-axis Low effort --> High effort
    y-axis Low value --> High value
    quadrant-1 Plan carefully
    quadrant-2 Do first
    quadrant-3 Nice to have
    quadrant-4 Question it
    Real UI screenshots: [0.1, 0.7]
    Real-document test set: [0.45, 0.9]
    Free hosted demo: [0.3, 0.65]
    Real tokenizer option: [0.3, 0.6]
    Borderless tables: [0.7, 0.7]
    Word headers and footnotes: [0.35, 0.5]
    API password: [0.2, 0.5]
    Equation to LaTeX: [0.9, 0.6]
    Right-to-left tests: [0.5, 0.3]
```

| # | Improvement | Why | Rough approach |
|---|---|---|---|
| 1 | Run the web app and API for real; take real screenshots | Closes the biggest honesty gap | Follow the check list in [09](09_reproducibility_guide.md) |
| 2 | Real-document evaluation set | Replaces tuned samples with honest scores | Collect public documents, write expected anchors |
| 3 | Free hosted demo | A link to show | Streamlit Community Cloud (`packages.txt` exists); see [deep dive: deployment](deep_dive/deployment_free.md) |
| 4 | Real tokenizer option | Exact counts for a chosen model | Optional `tiktoken` or similar behind a flag |
| 5 | Borderless table detection | Fewer broken columns | Column alignment of words across rows |
| 6 | Word headers, footers, footnotes, text boxes | Less lost content | Read the extra XML parts |
| 7 | API key or password | Safe sharing | Header token check in `api/main.py` |
| 8 | PDF equations to LaTeX | Chat tools could read formulas | Optional free model (for example a local formula recogniser) |
| 9 | Right-to-left and more OCR languages in tests | Wider coverage | Add samples and language data |
| 10 | Windows and macOS test runs | Wider coverage | CI matrix |
| 11 | CI on every push | Keeps the 131 tests honest | GitHub Actions running the test commands |
| 12 | Drag and drop of files into the desktop window | Faster opening | Optional `tkinterdnd2` |
| 13 | Package the desktop window as a single program | Run without Python knowledge | PyInstaller |
| 14 | Measure savings against chatbot readers | Turns a claim into a number | Same file through a chat tool and this tool, count tokens |

---
Previous: [11 Limitations and Known Issues](11_limitations_and_known_issues.md) · Next: [13 Troubleshooting](13_troubleshooting.md)
