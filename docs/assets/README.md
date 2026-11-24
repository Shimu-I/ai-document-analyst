# Figures and how they are regenerated

| File | Source | How |
|---|---|---|
| `01_architecture.png` ... `09_build_roadmap.png` | `src/*.mmd` (Mermaid) | `mmdc -i src/01_architecture.mmd -o 01_architecture.png -c src/mermaid.json -s 2 -b white` (needs Mermaid CLI: `npm i -g @mermaid-js/mermaid-cli`) |
| `banner.png`, `terminal.png`, `image_to_markdown.png` | `src/banner.html`, `src/terminal.html`, `src/image_to_markdown.html` | Open the HTML in a headless browser (Playwright) and take a screenshot at 2x scale |
| `tokens_json.png`, `fidelity.png` | `scripts/make_figures.py` | `pip install matplotlib && python scripts/make_figures.py` (measures live; reads `reports/fidelity.json`) |
| `sample_article.png` | `scripts/make_image_samples.py` | Input of the image-to-Markdown figure |

`terminal.png` shows real output of the command line. No screenshot of the Streamlit page exists yet: it should be added after the first local run
(`streamlit run app/streamlit_app.py`, convert a sample, capture the page).


## Diagram pictures for the web app

`scripts/make_diagrams.py` renders every Mermaid block in `docs/` to `docs/assets/diagrams/<document>_<n>.png` (needs `mmdc`). The Docs page of the web app shows these pictures, because Streamlit cannot draw Mermaid. Run the script again after editing a diagram and commit the new PNGs.
