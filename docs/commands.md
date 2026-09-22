# Commands and exit codes

Every command accepts an explicit `--receipt PATH`; there is no default store or
home-directory state. `--json` emits one structured object. Default output starts
with a status line followed by indented JSON with caller-supplied strings quoted.
`--version` and `--help` work without artifact paths.

| Command | Required inputs | Result |
| --- | --- | --- |
| `author` | `--root`, repeated `--file`, `--receipt`, `--reviewer`, `--label`, `--verdict`, `--notes-file` | Read all selected artifacts and publish a caller-authored receipt |
| `inspect` | `--receipt` | Validate and display stored data; do not inspect current artifacts |
| `check` | `--root`, repeated `--file`, `--receipt` | Compare the exact expected selection against stored bytes and modes |

Author also accepts repeated `--evidence TEXT` and explicit `--overwrite`. Verdicts
are caller text, not a fixed approval enum. Reviewer, label, and verdict must each
contain 1–1024 UTF-8 bytes. Notes can be empty, since this tool does not judge review
quality. Evidence references are opaque nonempty strings, at most 128 references
of 4096 UTF-8 bytes each. Their targets are never read or fetched.

`--notes-file PATH` requires a UTF-8 regular file. `--notes-file -` reads explicitly
selected stdin until EOF and can wait for its producer. No implicit stdin read
occurs. Other selected special files, including FIFOs, are rejected without a
blocking read. Notes are capped at 1 MiB.

`--max-files` defaults to 256, accepts 1–10000, and bounds both the expected selection
and receipt records. `--max-bytes` defaults to 64 MiB and bounds the total current
artifact bytes read; zero allows only empty artifacts. Receipts have a fixed 8 MiB
limit. A limit error produces no partial comparison or successful publication.

| Exit | Status | Meaning |
| ---: | --- | --- |
| 0 | `written` / `valid` | Receipt published, schema validated by inspect, or current bytes/modes matched by check |
| 3 | `stale` | At least one selected artifact changed or is missing |
| 4 | `missing` | The requested receipt does not exist |
| 2 | `invalid` | Invalid input/schema/selection, unsafe or unreadable path, budget failure, publication error, or I/O failure |

Argparse usage errors and output-stream failures can return 2 without a JSON result.
Check exit 0 means current bytes and modes match, including when the stored verdict
rejects the work. No verdict policy or approval gate is applied.
Always check the exit code. A check result names its `scope`; inspect explicitly
uses `receipt_schema_only` and cannot establish currentness. Check includes the
original review fields, expected/current file counts, and path-specific findings.
