# Review Receipts

Bind a caller-authored review to the exact bytes and POSIX modes of selected files,
then check whether those files still match, keeping reviewer identity, label,
verdict, notes, and opaque evidence references in a portable JSON receipt.

> **Status:** public Apache-2.0 reference implementation, deprecated for new Claude Code
> integrations as of 2026-09-22. Not a claim that Claude Code replaces every capability; no
> ongoing feature work or support is promised.

## What it does

- `author` reads the explicitly selected files and writes a receipt binding their
  bytes and modes (SHA-256) to the caller's review text.
- `inspect` validates and displays a stored receipt without reading current files.
- `check` compares the exact expected file selection against the receipt and reports
  whether the files still match.

## Why it exists

Knowing that a review exists, or that it is newer than the reviewed files, does not
show that those files are unchanged since the review. A receipt binds the review to
exact bytes and modes, so a later edit or mode change makes `check` report it as
stale. Check requires the expected file selection again, so dropping a file record
from a receipt cannot silently narrow the caller's requested check.

## Install

Version 0.1.0rc1. Requires Python 3.9+ on macOS or Linux with descriptor-relative
filesystem operations. The single executable has no packages, Git dependency,
network calls, or model integration. Windows is unsupported.

```sh
git clone https://github.com/AdityaVikramDalmia/flightdeck-review-receipts.git
cd flightdeck-review-receipts
make install PREFIX="$HOME/.local"
```

`bin/review-receipts` runs directly and can be copied independently. `DESTDIR`
supports staged installation.

## Quick use

`make demo` runs a self-contained synthetic example. Against your own files (the
receipt's parent directory must already exist):

```sh
review-receipts author --root ./project \
  --file docs/design.md --file config/settings.json \
  --receipt ./reviews/design.json \
  --reviewer 'Example reviewer' --label 'Design review' --verdict 'Needs changes' \
  --notes-file ./review-notes.txt --evidence 'issue:example-42'

review-receipts inspect --receipt ./reviews/design.json --json

review-receipts check --root ./project \
  --file docs/design.md --file config/settings.json \
  --receipt ./reviews/design.json --json
```

Use `--notes-file -` to explicitly read UTF-8 notes from stdin. Unicode, line
endings, and trailing newlines are preserved. Paths stored in receipts are relative;
checking a relocated root requires the same selected relative paths.

An existing receipt is preserved unless author receives `--overwrite`. Replacing
a receipt is a new caller assertion; inspect the changes before doing so.

See [documentation](docs/README.md) for schema, scope, storage, and failure behavior,
and [provenance](PROVENANCE.md) for the adaptation.

## Limits

- A matching hash proves only that selected bytes match the receipt. It does not
  prove the review is correct, authenticate its author, authorize a release, or turn
  a caller's verdict into an approval.
- The tool never executes reviewed content or fetches evidence references.
- These are explicit files, not a directory inventory; new, unselected files are
  outside scope.
- File and ancestor symlinks inside the selected root are refused.
- The tool does not retain old receipts automatically.

## Test

```sh
make test
make demo
```

The synthetic suite has been executed on macOS with Python 3.14 and in an
unprivileged Alpine Linux container.

## License and maintenance

Copyright 2026 Aditya Dalmia. Licensed under [Apache-2.0](LICENSE), with
[attribution](NOTICE) and [source provenance](PROVENANCE.md). This is a public
reference implementation, deprecated for new Claude Code integrations as of 2026-09-22. See the [release preparation index](docs/release/README.md),
[contributing guide](CONTRIBUTING.md), and [security contact](SECURITY.md).
