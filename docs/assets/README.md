# Assets

| File | Status | Notes |
|---|---|---|
| `wordmark.svg` | ✅ Real, in use | Plain black-and-white text wordmark ("PROJECT METAL"), not a designed logo — built to render safely inside GitHub's README SVG sanitizer (plain `<text>`, no external fonts/filters/scripts). Rendered and visually checked before being committed (via `cairosvg`, not just assumed from markup). Replace with a real designed logo whenever that work happens — same filename, same two-line/bold/black-on-white brief if that direction is kept, or a new brief if not. |
| `screenshots/` | ❌ Does not exist yet | Create this folder when there's a real, visually-designed screen worth capturing. See the main `README.md`'s "Screenshots & Demo" section for the priority order (customer flow first, then the marketplace/booking mechanic, then the native app). |
| `demo/` | ❌ Does not exist yet | Same as above. Prefer a short `.gif` for anything committed directly to the repo (renders inline on GitHub) — a large `.mp4` bloats the repo and belongs hosted externally (YouTube/Loom) with a link instead. |

No placeholder or fabricated images live in this repo. If a screenshot exists here, it's a real screenshot of the real app at that commit — not a mockup standing in for one.
