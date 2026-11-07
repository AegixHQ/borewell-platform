# Assets

| File | Status | Notes |
|---|---|---|
| `wordmark.svg` | ✅ Real, in use | Plain black-and-white text wordmark ("PROJECT METAL"), not a designed logo — built to render safely inside GitHub's README SVG sanitizer (plain `<text>`, no external fonts/filters/scripts). Rendered and visually checked before being committed (via `cairosvg`, not just assumed from markup). Replace with a real designed logo whenever that work happens — same filename, same two-line/bold/black-on-white brief if that direction is kept, or a new brief if not. |
| `screenshots/app/` | ✅ Real screenshots | 12 renders of `apps/borewell-native` (390×844, in-memory demo backend, map tiles blocked so maps are grey). Index in that folder's own `README.md`. |
| `demo/` | ❌ Does not exist yet | Same as above. Prefer a short `.gif` for anything committed directly to the repo (renders inline on GitHub) — a large `.mp4` bloats the repo and belongs hosted externally (YouTube/Loom) with a link instead. |

No placeholder or fabricated images stand in for real app screenshots in this repo. The earlier design-mockup JPEGs were removed upstream; the screenshots above are of the running app, not mockups.
