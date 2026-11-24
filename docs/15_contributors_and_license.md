# 15 - Contributors and License

## Contributors

| Name | Role | Responsibility |
|---|---|---|
| `<AUTHOR NAME>` (placeholder, to be filled in) | Project owner | Direction, review, publishing |
| An AI assistant (Claude) | Development helper | Wrote and tested code and documents in the build sessions, under the owner's direction |

The owner's name and GitHub account are not recorded anywhere in the repository yet (`<AUTHOR NAME>` and `<GITHUB-USERNAME>` are placeholders in the README and portfolio page). Fill them in before publishing. Which parts were written by hand and which were adapted is for the owner to state; the portfolio page has a "My Contribution" section for it.

## Contributing

The project is a working prototype and accepts issues and pull requests once it is published. No separate contribution guide exists yet; these rules are the practical ones:

1. **Report a problem** with the exact command or options, the full message, `python3 --version`, `tesseract --version`, and a small non-confidential file that reproduces it.
2. **Add a failing case first.** A new row in `scripts/corner_cases.py`, or a test in `tests/`, shows the problem and keeps the fix in place.
3. **Run the checks** before sending a change:
   ```bash
   python -m unittest discover -s tests -t .
   python scripts/corner_cases.py
   ```
4. **Keep the wording impersonal** in documents and interface text (no "you"), and keep every number in the documents traceable to a script or test.
5. **Do not commit** real documents, keys or history files.

## License

The project is released under the **MIT License** (file `LICENSE`, copyright line "2026 AI Document Analyst contributors"). Third-party libraries keep their own licenses; see [14 References and Acknowledgements](14_references_and_acknowledgements.md). Before publishing, the copyright line can be changed to the owner's name.

---
Previous: [14 References and Acknowledgements](14_references_and_acknowledgements.md) · Back to [index](README.md)
