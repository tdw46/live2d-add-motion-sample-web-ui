# CLAUDE.md

The AI-agent guide for this project is @AGENTS.md (shared with Codex and
other agents). Read it before working. Key points:

- Everything under `models/` is generated. Never edit it directly — edit
  `motion-defs/<model>.py` and re-run `tools/gen_motions.py`
- Follow the workflow in AGENTS.md ("The typical request, and what to do")
- Definition of Done: `tools/validate_motions.py` exits 0 + visual check of
  the `tools/verify_browser.sh` screenshots
