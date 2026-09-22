# Receipt schema and publication

Version 1 has exactly these top-level keys:

| Field | Meaning |
| --- | --- |
| `version` | Integer `1` |
| `created_at` | UTC author timestamp, `YYYY-MM-DDTHH:MM:SS.ffffffZ` |
| `algorithm` | `sha256` |
| `binding` | `bytes-and-posix-mode` |
| `review` | Exact reviewer, label, verdict, notes, and evidence list supplied by the caller |
| `files` | Nonempty, unique, lexically sorted artifact records |

Each file record has exactly `path`, `size`, `sha256`, and `mode`. The digest is 64
lowercase hexadecimal characters. Size is a nonnegative integer and mode is an
integer from 0 through octal 07777. Booleans do not count as integers. Unknown
fields, duplicate JSON keys, malformed timestamps, invalid paths, duplicate file
records, unsorted records, and unsupported bindings are errors.

Notes are decoded as UTF-8 without newline conversion and stored as a JSON string.
JSON escaping can change their serialized representation but not their decoded
Unicode text, line endings, or trailing newlines. Receipts store no root location;
review text and evidence are caller-provided and may themselves mention locations.
No secrets, runtime state, or other metadata are discovered automatically.

The destination parent must exist and is explicitly selected by the caller. The
receipt cannot alias a selected artifact, including an existing case alias or hard
link. Artifact/destination inode aliasing is checked while each artifact is open
and again before publication. The canonical selected pathname is protected
independently of its inode, so atomically replacing a selected file does not make
that path an eligible receipt destination. Existing receipt symlinks and
non-regular files are refused. The receipt can
live inside the root if it is not one of the selected artifacts; no directory-wide
inventory or implicit exclusion is involved.

Publication writes complete JSON to a unique temporary file beside the destination,
flushes and `fsync`s it, then publishes with an atomic hard link when overwrite is
not requested. Concurrent no-overwrite authors have one winner. `--overwrite` uses
atomic replacement. The destination directory is then `fsync`ed. Temporary names
are removed on ordinary Python unwinding. New receipt files use mode 0600, subject
to the process umask. The tool never edits selected artifacts.

Use trusted local filesystem semantics. Default publication requires hard-link
support; network filesystems, shared multi-host stores, and Windows are unsupported.
A flush request is not a hardware/power-loss certification. SIGKILL or termination
that bypasses Python cleanup can leave `.review-receipts-*.tmp` files. Stop authors
and inspect these files before deleting them. They are never loaded automatically.

A directory flush or stdout failure can happen after a complete receipt became
visible. A nonzero result therefore does not prove nothing was written: inspect
the destination before retrying. Output is explicitly flushed; a closed or broken
stream cannot yield a successful exit. Concurrent intentional overwrites are not
serialized and can replace one another; coordinate those updates externally.

Reads may update access times according to filesystem policy.
File reads compare descriptor/path metadata before and after hashing to detect
many concurrent changes. Multiple files are not an atomic snapshot, and a change
reverted between observations or an external directory swap can escape those checks.
Stop writers when taking or validating a review binding. Descriptor traversal
prevents stored paths from following symlinks, but this is not a sandbox against
hostile processes that can concurrently replace the selected filesystem hierarchy.
