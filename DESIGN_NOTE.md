# Design note: type conversion is now opt-in

**What I first built.** My first draft converted every cell it could into a number, boolean or null, because that
seemed the most useful thing a CSV-to-JSON tool could do. There was no flag; it simply happened.

**What testing on awkward input showed.** I ran it on a small set of deliberately nasty files. The worst result
was silent corruption. A file with a `zip` column holding `02134` and `00501` came out as `2134` and `501`, and a
phone-style value `007` came out as `7`. Nothing warned me; the output was valid JSON and looked plausible. The
same draft also turned `1_000` into `1000` (Python accepts underscores in numbers), turned `" 42 "` into `42`, and
wrote `NaN` and `Infinity` into the output, which is not valid JSON at all. Identifiers like zip codes, account
numbers and phone numbers are very common in CSV files, so the default was wrong for exactly the data people
tend to have.

**What I changed.**
1. Values now stay as text by default. Conversion happens only with `--infer-types`.
2. Even then, the rules are strict: only text that converts and prints back identically becomes a number
   (`42`, `-3`, `2.5`, `1e3`). Leading zeros, underscores, spaces, signs like `+5`, `NaN`, `Infinity` and numbers
   too large to be finite all stay as text. The output is also written with `allow_nan=False`, so invalid JSON
   cannot be produced.

**Trade-off.** Someone who wants real numbers must now type `--infer-types`, and a column such as `007` will
never become a number even if they wanted it to. I chose that because a tool that needs one extra flag is a
small annoyance, while a tool that quietly rewrites identifiers is a data-loss bug. I considered per-column
control (for example `--text zip`) and rejected it for now as more interface than a one-job tool needs.

**Other fixes from the same round of testing** (these were bugs rather than design choices): duplicate headers
no longer overwrite each other, ragged rows no longer lose fields silently, and an empty file, a Latin-1 file and
a byte-order mark each produce a clear message or correct output instead of a traceback or a corrupted key.
Each has a test, and I confirmed the tests fail if I put the leading-zero bug back.
