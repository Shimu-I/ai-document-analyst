# 15 - Contributors and License

## Contributors

| Name | Role | Responsibility |
|---|---|---|
| **Shimu-I** ([@Shimu-I](https://github.com/Shimu-I)) | Project owner | Idea, direction, review, testing on a real machine, publishing |
| **Claude** (AI assistant by Anthropic) | Development partner | Wrote and tested code and documents in the build sessions, under the owner's direction |

Repository: <https://github.com/Shimu-I/ai-document-analyst>. Which parts were written by hand and which were adapted is for the owner to state; the portfolio page has a "My Contribution" section for it.

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

The project is released under the **MIT License** (file `LICENSE`, copyright line "2026 Shimu-I and Claude (AI assistant by Anthropic)"). Third-party libraries keep their own licenses; see [14 References and Acknowledgements](14_references_and_acknowledgements.md).

---
Previous: [14 References and Acknowledgements](14_references_and_acknowledgements.md) · Back to [index](README.md)
