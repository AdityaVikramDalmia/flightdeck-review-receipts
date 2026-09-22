# Provenance

Adapted from the review-receipt path/template/check mechanism in
`bin/grill-brief.sh`, its shared `bin/lib/grill.sh` contract, and the corresponding
receipt assertions in `bin/grill-brief-test.sh`, source revision
`494799eea3b9e7ce8686506a288c297ccf96be8d`.

This standalone implementation deliberately changes the mechanism. The source
checked whether a sibling receipt existed and was at least as new as its brief;
it did not interpret review prose. This tool binds explicitly selected current
file bytes and modes using SHA-256, validates a portable JSON envelope, preserves
caller-supplied review text, and checks an independently supplied expected file set.

It does not copy project-specific review questions, fences, policy IDs, model
routing, dispatch behavior, recipe linting, or reviewer automation. No private
runtime state is included. Examples and tests contain only synthetic inputs.

Private candidate; Apache-2.0 licensed; public launch deferred. The owner selected Apache-2.0 on 2026-09-22; public launch remains deferred.
