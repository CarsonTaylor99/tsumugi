# Engine signatures

`engines.json` is **data, not code** — adding support for detecting a new engine should be a
data edit, never a rebuild. Stage 0 reads it, scores each engine by matched evidence, and
reports confidence plus the evidence list to the user.

Evidence kinds:

| kind | meaning |
|---|---|
| `file` | a filename or glob present in the install dir |
| `magic` | leading bytes of a named file |
| `exe_string` | an ASCII/UTF-16 string present in the main executable |
| `dir` | a directory that must exist |

Each entry carries a weight; the sum of matched weights, normalised, is the confidence.
Never auto-select below a configured threshold — report and ask.

`engines.json` is a stub until Phase 1 (see `docs/08-roadmap.md`).
