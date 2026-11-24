# Changelog

Each update script (`apply_update_vNN.sh`) contains **everything** from the original project up to that version, so only the **latest** one needs to be run. The script records what was applied in `.update_log` (project folder) and prints it.

| Version | Content |
|---|---|
| v1 | Multi-page web app (Home, Convert, Dashboard, Guide), conversion history, equations / tables / diagrams kept, warm palette |
| v2 | Documentation restructured into 14 numbered documents with Mermaid diagrams; old chapters moved to `docs/deep_dive/` |
| v3 | Text inside pictures read with OCR (slides saved as images), model chip, soft light and Dim themes |
| v4 | Slide layout kept for figure and picture text (bullets, nesting); preview hides pictures that have text, optional original beside text |
| v5 | Type scale (16 / 36 / 30 px), wrapping top bar with in-page links, responsive CSS, upload checks and clearer errors on Convert |
| v6 | New landing layout on Home; chip shows the open-source AI model status; project activity in the footer |
| v7 | Documentation page in the app (sections, contents, search, previous / next, diagram pictures); document 15 Contributors and License |
| v8 | Page content centred on wide screens (it sat at the left edge) |
| v9 | Desktop window (Tkinter) with linked reading of slide and text; English and Bengali OCR (`auto`); slide-by-slide reading for PDF, PowerPoint, Word and images |
| v10 | Desktop documentation (features, install, user guide, limits, troubleshooting), `scripts/run_desktop.sh` launcher, diagram pictures refreshed |
| v11 | Top bar: theme switch no longer wraps, readable "Open the app" button; update message corrected |

Versions v1 to v6 were delivered as separate files earlier; this list was written afterwards from the project history.
