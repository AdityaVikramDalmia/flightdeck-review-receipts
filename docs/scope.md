# Selection, paths, and review meaning

The root is an explicit existing directory. Its final component cannot be a
symlink; user-supplied ancestor paths are resolved before opening it. After opening
the root, each artifact is reached through directory file descriptors with
`O_NOFOLLOW` for every component. Final entries must be regular files. Symlinks,
directories, sockets, devices, and FIFOs are not reviewable artifacts in version 1.

Each `--file` is a canonical, root-relative UTF-8 path. Empty, absolute, dot, parent,
duplicate, or empty-component paths are refused, as are NUL characters. Paths are
limited to 4096 UTF-8 bytes and 64 components. Spaces, Unicode, newlines, and literal
backslashes can occur in filenames and are escaped in JSON. Non-UTF-8 filesystem
names are unsupported. Path spellings are preserved; the tool does not normalize
Unicode or letter case beyond the host filesystem's behavior.

The same expected set must be passed to check. A receipt with an omitted, added,
duplicate, or changed path cannot match the caller's original selection. Receipts
are validated before any artifact is opened, so malformed stored traversal paths
cannot escape the explicit root. Only the supplied files are covered. There are
no automatic exclusions, recursive scans, Git ignore rules, or claims that all
files in a project were reviewed. Adding an unselected file does not stale a receipt.

The binding includes exact bytes, byte size, and POSIX permission/set-ID/sticky
bits. Changing a selected file's contents or mode makes the receipt stale. Timestamps,
ownership, ACLs, extended attributes, parent-directory modes, and hard-link topology
are not bound. Hardlinked regular files remain ordinary selected paths. A rename
makes the old selected path missing; use a newly authored receipt to change scope.

A missing artifact produces a stale finding. A missing or unreadable root is an
invalid inspection, since it may represent a wrong location. Replacing a reviewed
file or ancestor with a symlink is invalid rather than followed. Root-relative
paths permit deliberate relocation; bytes and modes still must match.

Hashes are evidence of equality against a reference, not signatures or proof of
review quality. Anyone able to edit a receipt can forge metadata, hashes, and a
consistent selection. The caller must select the expected files independently
and protect the reference according to their own process. Author hashes the
current files when invoked; it cannot prove those are the bytes a person previously
read. The timestamp records author invocation in UTC and does not drive currentness.
A matching rejected verdict remains a matching rejected verdict; no approval is inferred.
