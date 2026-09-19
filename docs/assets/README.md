# Assets

| File | Status | Notes |
|---|---|---|
| `wordmark.svg` | ✅ Real, in use | Plain black-and-white text wordmark ("PROJECT METAL"), not a designed logo — built to render safely inside GitHub's README SVG sanitizer (plain `<text>`, no external fonts/filters/scripts). Rendered and visually checked before being committed (via `cairosvg`, not just assumed from markup). Replace with a real designed logo whenever that work happens — same filename, same two-line/bold/black-on-white brief if that direction is kept, or a new brief if not. |
| `screenshots/borewell-ui-mockups-full.jpeg` | 🎨 Design mockup (target UI) | Not a screenshot of the running app. Full-flow design mockups covering both Customer App and Contractor App — dashboards, quotation workflow, resource/fleet management. Reference for Milestone 3 implementation, not evidence of build status. |
| `screenshots/borewell-ui-screens-mobile.jpeg` | 🎨 Design mockup (target UI) | Not a screenshot of the running app. Mobile-native screen designs for the Customer App journey (sign-in, job type selection, quotation, tracking) plus key Contractor App interactions. |
| `demo/` | ❌ Does not exist yet | Same as above. Prefer a short `.gif` for anything committed directly to the repo (renders inline on GitHub) — a large `.mp4` bloats the repo and belongs hosted externally (YouTube/Loom) with a link instead. |

No placeholder or fabricated images stand in for real app screenshots in this repo. The two design mockups above are clearly labeled as mockups, not screenshots — when a real screenshot of the running app exists, it goes here labeled as such, and the mockups stay only as design reference until then.
