# Review Receipts

> **Deprecated for new Claude Code integrations — 2026-09-22.** Retained as an
> Apache-2.0 public reference implementation. This is a maintainer status
> decision, not a claim that Claude
> Code replaces every capability. No ongoing feature work or support is promised.

Bind a caller-authored review to the exact bytes and POSIX modes of selected files,
then check whether those files still match. Preserve reviewer identity, label,
verdict, notes, and opaque evidence references in a portable JSON receipt.

**Public reference implementation: 0.1.0rc1; Apache-2.0 licensed; deprecated for new Claude Code integrations as of 2026-09-22.** Requires Python
3.9+ on macOS or Linux with descriptor-relative filesystem operations. The single
executable has no packages, Git dependency, network calls, or model integration.
Windows is unsupported.

A matching hash proves only that selected bytes match the receipt. It does not
prove the review is correct, authenticate its author, authorize a release, or turn
a caller's verdict into an approval. The tool never executes reviewed content or
fetches evidence references.

## Author and check

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

The receipt's parent directory must already exist. Check requires the expected
file selection again, so dropping a file record from a receipt cannot silently
narrow the caller's requested check. These are explicit files, not a directory
inventory; new, unselected files are outside scope.

Use `--notes-file -` to explicitly read UTF-8 notes from stdin. Unicode, line
endings, and trailing newlines are preserved. File and ancestor symlinks inside
the selected root are refused. Paths stored in receipts are relative; checking a
relocated root requires the same selected relative paths.

An existing receipt is preserved unless author receives `--overwrite`. Replacing
a receipt is a new caller assertion; inspect the changes before doing so. The
tool does not retain old receipts automatically.

## Install and verify

```sh
make test
make demo
make install PREFIX="$HOME/.local"
```

`bin/review-receipts` runs directly and can be copied independently. `DESTDIR`
supports staged installation. The synthetic suite has been executed on macOS with
Python 3.14 and in an unprivileged Alpine Linux container.

See [documentation](docs/README.md) for schema, scope, storage, and failure behavior,
and [provenance](PROVENANCE.md) for the adaptation.

## License and maintenance

Copyright 2026 Aditya Dalmia. Licensed under [Apache-2.0](LICENSE), with
[attribution](NOTICE) and [source provenance](PROVENANCE.md). This is a public
reference implementation, deprecated for new Claude Code integrations as of 2026-09-22. See the [release preparation index](docs/release/README.md),
[contributing guide](CONTRIBUTING.md), and [security contact](SECURITY.md).
