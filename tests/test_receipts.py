import concurrent.futures
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/review-receipts"
loader = importlib.machinery.SourceFileLoader("receipts", str(CLI))
spec = importlib.util.spec_from_loader(loader.name, loader)
MODULE = importlib.util.module_from_spec(spec)
loader.exec_module(MODULE)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="review receipts ")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "selected root"
        self.root.mkdir()
        (self.root / "a.txt").write_bytes(b"reviewed bytes\x00\xff\n")
        (self.root / "nested").mkdir()
        (self.root / "nested/b.txt").write_text("second artifact\n")
        self.receipt = self.base / "review.json"
        self.notes = self.base / "notes.txt"
        self.note_text = "Review résumé ☃\r\n\nSecond line.\n\n"
        self.notes.write_bytes(self.note_text.encode())

    def command(self, action, *extra, paths=None, binary=CLI):
        cmd = [str(binary), action, "--json", "--receipt", str(self.receipt)]
        if action != "inspect":
            cmd += ["--root", str(self.root)]
            for path in paths or ["a.txt", "nested/b.txt"]:
                cmd += ["--file", path]
        if action == "author":
            cmd += ["--reviewer", "Reviewer ☃", "--label", "design review", "--verdict", "needs changes",
                    "--notes-file", str(self.notes), "--evidence", "opaque:review/42"]
        return cmd + list(extra)

    def run_cli(self, action, *extra, expected=0, paths=None, binary=CLI, input=None):
        proc = subprocess.run(self.command(action, *extra, paths=paths, binary=binary), capture_output=True,
                              text=True, input=input, timeout=10)
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        return json.loads(proc.stdout)

    def author(self):
        return self.run_cli("author")

    def edit(self, change):
        row = json.loads(self.receipt.read_text())
        change(row)
        self.receipt.write_text(json.dumps(row))

    def test_author_inspect_check_preserve_review_verbatim(self):
        self.author()
        receipt = self.run_cli("inspect")["receipt"]
        self.assertEqual(receipt["review"]["notes"], self.note_text)
        self.assertEqual(receipt["review"]["reviewer"], "Reviewer ☃")
        self.assertEqual(receipt["review"]["verdict"], "needs changes")
        self.assertEqual(receipt["review"]["evidence"], ["opaque:review/42"])
        checked = self.run_cli("check")
        self.assertEqual(checked["status"], "valid")
        self.assertEqual(checked["review"], receipt["review"])
        self.assertEqual(checked["checked_files"], 2)
        self.assertEqual(stat.S_IMODE(self.receipt.stat().st_mode), 0o600)

    def test_single_file_and_binary_content_are_supported(self):
        self.run_cli("author", paths=["a.txt"])
        self.assertEqual(self.run_cli("check", paths=["a.txt"])["status"], "valid")

    def test_changed_bytes_are_stale_even_with_restored_mtime(self):
        self.author()
        artifact = self.root / "a.txt"
        previous = artifact.stat()
        artifact.write_bytes(b"different bytes!\n")
        os.utime(artifact, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        result = self.run_cli("check", expected=3)
        self.assertEqual(result["status"], "stale")
        self.assertIn("sha256", result["findings"][0]["fields"])

    def test_timestamp_only_change_is_valid_but_mode_change_is_stale(self):
        self.author()
        os.utime(self.root / "a.txt", (100, 100))
        self.run_cli("check")
        (self.root / "a.txt").chmod(0o700)
        result = self.run_cli("check", expected=3)
        self.assertEqual(result["findings"][0]["fields"], ["mode"])

    def test_deleted_or_renamed_artifact_is_stale(self):
        self.author()
        (self.root / "a.txt").rename(self.root / "renamed.txt")
        result = self.run_cli("check", expected=3)
        self.assertEqual(result["findings"], [{"path": "a.txt", "state": "missing", "fields": []}])
        (self.root / "nested/b.txt").unlink()
        self.assertEqual(len(self.run_cli("check", expected=3)["findings"]), 2)

    def test_missing_receipt_is_distinct_from_missing_author_input(self):
        self.assertEqual(self.run_cli("check", expected=4)["status"], "missing")
        self.assertEqual(self.run_cli("inspect", expected=4)["status"], "missing")
        (self.root / "a.txt").unlink()
        self.assertEqual(self.run_cli("author", expected=2)["status"], "invalid")
        self.assertFalse(self.receipt.exists())

    def test_expected_selection_prevents_silently_omitted_receipt_files(self):
        self.author()
        self.edit(lambda row: row["files"].pop())
        self.assertEqual(self.run_cli("check", expected=2)["status"], "invalid")

    def test_extra_unselected_files_are_outside_scope(self):
        self.author()
        (self.root / "new.txt").write_text("not in the explicit review")
        self.run_cli("check")
        self.run_cli("check", paths=["a.txt", "nested/b.txt", "new.txt"], expected=2)

    def test_symlink_leaves_and_ancestors_never_follow_outside_root(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret").write_text("outside secret")
        (self.root / "link").symlink_to(outside / "secret")
        (self.root / "ancestor").symlink_to(outside, target_is_directory=True)
        self.run_cli("author", paths=["link"], expected=2)
        self.run_cli("author", paths=["ancestor/secret"], expected=2)
        self.assertFalse(self.receipt.exists())
        self.author()
        (self.root / "a.txt").unlink()
        (self.root / "a.txt").symlink_to(outside / "secret")
        self.run_cli("check", expected=2)
        self.assertEqual((outside / "secret").read_text(), "outside secret")

    def test_root_symlink_is_refused_and_root_can_relocate(self):
        self.author()
        moved = self.base / "moved root"
        self.root.rename(moved)
        self.root.symlink_to(moved, target_is_directory=True)
        self.run_cli("check", expected=2)
        self.root = moved
        self.run_cli("check")
        self.assertNotIn(str(self.base), self.receipt.read_text())

    def test_malformed_receipts_and_unsafe_paths_fail_before_artifact_reads(self):
        self.author()
        original = self.receipt.read_text()
        for value in ("", "{", "[]", "NaN", '{"version":1,"version":1}', "[" * 1500 + "0" + "]" * 1500):
            self.receipt.write_text(value)
            self.run_cli("check", expected=2)
        for path in ("../secret", "/absolute", "nested//b", "./a", "nested/../a", "x\x00y"):
            self.receipt.write_text(original)
            self.edit(lambda row: row["files"][0].update(path=path))
            with mock.patch.object(MODULE, "snapshot_file", side_effect=AssertionError("invalid paths must not be read")):
                with self.assertRaises(MODULE.ReceiptError):
                    MODULE.load_receipt(self.receipt, 256)
            self.run_cli("check", expected=2)

    def test_invalid_schema_types_duplicates_and_metadata_fail_closed(self):
        self.author()
        original = self.receipt.read_text()
        mutations = [lambda r: r.update(version=True), lambda r: r.update(algorithm="md5"),
                     lambda r: r.update(binding="bytes-only"), lambda r: r.update(created_at="yesterday"),
                     lambda r: r.update(files=[]), lambda r: r["files"].append(r["files"][0]),
                     lambda r: r["files"][0].update(size=True), lambda r: r["files"][0].update(mode=-1),
                     lambda r: r["files"][0].update(sha256="z" * 64),
                     lambda r: r["review"].update(reviewer=""), lambda r: r["review"].update(extra="unknown"),
                     lambda r: r["review"].update(evidence="not a list")]
        for mutation in mutations:
            self.receipt.write_text(original)
            self.edit(mutation)
            self.run_cli("inspect", expected=2)

    def test_no_overwrite_and_concurrent_authors_have_one_winner(self):
        def author(_):
            return subprocess.run(self.command("author"), capture_output=True, timeout=10).returncode
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            codes = list(pool.map(author, range(6)))
        self.assertEqual(codes.count(0), 1)
        self.assertEqual(codes.count(2), 5)
        original = self.receipt.read_bytes()
        self.run_cli("author", expected=2)
        self.assertEqual(self.receipt.read_bytes(), original)
        self.run_cli("author", "--overwrite", "--verdict", "accepted")
        self.assertEqual(self.run_cli("inspect")["receipt"]["review"]["verdict"], "accepted")
        self.assertEqual(list(self.base.glob(".review-receipts-*.tmp")), [])

    def test_receipt_cannot_overwrite_reviewed_artifact_or_hardlink_alias(self):
        original = (self.root / "a.txt").read_bytes()
        self.receipt = self.root / "a.txt"
        self.run_cli("author", "--overwrite", expected=2)
        self.receipt = self.base / "alias"
        os.link(self.root / "a.txt", self.receipt)
        self.run_cli("author", "--overwrite", expected=2)
        self.assertEqual((self.root / "a.txt").read_bytes(), original)

    def test_case_alias_receipt_cannot_overwrite_selected_artifact(self):
        selected = self.root / "Selected.txt"
        selected.write_text("retain these reviewed bytes")
        alias = self.root / "selected.txt"
        if not alias.exists():
            self.skipTest("filesystem distinguishes these case variants")
        self.receipt = alias
        self.run_cli("author", "--overwrite", paths=["Selected.txt"], expected=2)
        self.assertEqual(selected.read_text(), "retain these reviewed bytes")

    def test_receipt_symlink_cannot_overwrite_target(self):
        target = self.base / "target"
        target.write_text("retained")
        self.receipt.symlink_to(target)
        self.run_cli("author", "--overwrite", expected=2)
        self.run_cli("inspect", expected=2)
        self.assertEqual(target.read_text(), "retained")

    def test_file_and_notes_limits_leave_no_partial_receipt(self):
        for flags in (("--max-files", "1"), ("--max-bytes", "1")):
            self.run_cli("author", *flags, expected=2)
            self.assertFalse(self.receipt.exists())
        self.notes.write_bytes(b"x" * (MODULE.NOTES_LIMIT + 1))
        self.run_cli("author", expected=2)
        self.assertFalse(self.receipt.exists())

    def test_special_files_are_rejected_without_blocking(self):
        pipe = self.root / "pipe"
        os.mkfifo(pipe)
        self.run_cli("author", paths=["pipe"], expected=2)
        self.run_cli("author", "--notes-file", str(pipe), expected=2)
        os.mkfifo(self.receipt)
        self.run_cli("inspect", expected=2)

    def test_stdin_notes_preserve_unicode_multiline_and_trailing_newlines(self):
        notes = "Notes ☃\n\nNo synthesized verdict.\n\n"
        self.run_cli("author", "--notes-file", "-", input=notes)
        self.assertEqual(self.run_cli("inspect")["receipt"]["review"]["notes"], notes)

    def test_invalid_utf8_notes_and_closed_stdin_are_errors(self):
        self.notes.write_bytes(b"\xff")
        self.run_cli("author", expected=2)
        proc = subprocess.run(self.command("author", "--notes-file", "-"), preexec_fn=lambda: os.close(0),
                              capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(b"Traceback", proc.stderr)
        self.assertFalse(self.receipt.exists())

    def test_publication_failure_preserves_previous_receipt(self):
        self.author()
        previous = self.receipt.read_bytes()
        receipt = json.loads(previous)
        with mock.patch.object(MODULE.os, "replace", side_effect=OSError("injected write failure")):
            with self.assertRaises(OSError):
                MODULE.publish(self.receipt, receipt, True, set())
        self.assertEqual(self.receipt.read_bytes(), previous)
        self.assertEqual(list(self.base.glob(".review-receipts-*.tmp")), [])

    def test_broken_and_closed_stdout_fail_honestly_after_publication(self):
        for kind in ("closed", "broken"):
            self.receipt = self.base / (kind + ".json")
            if kind == "closed":
                proc = subprocess.run(self.command("author"), preexec_fn=lambda: os.close(1),
                                      stderr=subprocess.PIPE, timeout=10)
            else:
                read, write = os.pipe()
                os.close(read)
                try:
                    proc = subprocess.run(self.command("author"), stdout=write, stderr=subprocess.PIPE, timeout=10)
                finally:
                    os.close(write)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertNotIn(b"Traceback", proc.stderr)
            self.assertTrue(self.receipt.is_file())
            self.run_cli("check")

    @unittest.skipIf(os.geteuid() == 0, "root bypasses permission checks")
    def test_unreadable_artifact_and_unwritable_destination_fail(self):
        artifact = self.root / "a.txt"
        artifact.chmod(0)
        try:
            self.run_cli("author", expected=2)
        finally:
            artifact.chmod(0o600)
        directory = self.base / "unwritable"
        directory.mkdir()
        directory.chmod(0o500)
        self.receipt = directory / "receipt.json"
        try:
            self.run_cli("author", expected=2)
            self.assertFalse(self.receipt.exists())
        finally:
            directory.chmod(0o700)

    def test_file_change_during_hashing_never_produces_snapshot(self):
        actual_read = os.read
        changed = False
        artifact = self.root / "a.txt"
        def read_then_change(descriptor, size):
            nonlocal changed
            data = actual_read(descriptor, size)
            if data and not changed:
                changed = True
                artifact.write_bytes(b"x" * len(data))
            return data
        with MODULE.root_directory(self.root) as root:
            with mock.patch.object(MODULE.os, "read", side_effect=read_then_change):
                with self.assertRaisesRegex(MODULE.ReceiptError, "changed during reading"):
                    MODULE.snapshot_file(root, "a.txt", 1000)
        self.assertFalse(self.receipt.exists())

    def test_post_publication_flush_failure_does_not_hide_visible_receipt(self):
        self.author()
        receipt = json.loads(self.receipt.read_text())
        self.receipt.unlink()
        actual_fsync = os.fsync
        count = 0
        def fail_directory_flush(descriptor):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("injected directory flush failure after publication")
            return actual_fsync(descriptor)
        with mock.patch.object(MODULE.os, "fsync", side_effect=fail_directory_flush):
            with self.assertRaisesRegex(OSError, "after publication"):
                MODULE.publish(self.receipt, receipt, False, set())
        self.assertTrue(self.receipt.is_file())
        self.run_cli("check")
        self.assertEqual(list(self.base.glob(".review-receipts-*.tmp")), [])

    def test_executable_artifacts_and_evidence_are_never_executed(self):
        marker = self.base / "must-not-exist"
        script = self.root / "hook.sh"
        script.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\n")
        script.chmod(0o755)
        self.run_cli("author", "--evidence", str(script), paths=["hook.sh"])
        self.run_cli("check", paths=["hook.sh"])
        self.assertFalse(marker.exists())

    def test_oversized_receipt_and_empty_root_are_invalid(self):
        with self.receipt.open("wb") as output:
            output.truncate(MODULE.RECEIPT_LIMIT + 1)
        self.run_cli("inspect", expected=2)
        self.receipt.unlink()
        self.run_cli("author", "--root", "", expected=2)
        self.assertFalse(self.receipt.exists())

    def test_copied_and_installed_command_is_independent(self):
        copy = self.base / "copied review tool"
        shutil.copy2(CLI, copy)
        self.run_cli("author", binary=copy)
        prefix = self.base / "installed tools"
        subprocess.run(["make", "install", "PREFIX=" + str(prefix)], cwd=ROOT, check=True, capture_output=True)
        self.run_cli("check", binary=prefix / "bin/review-receipts")

    def test_destination_selected_path_stays_protected_after_artifact_replacement(self):
        import argparse
        selected = self.root / "a.txt"
        original = selected.read_bytes()
        replacement = self.base / "replacement.txt"
        replacement.write_bytes(b"new bytes from a concurrent writer")
        args = argparse.Namespace(command="author", receipt=str(selected), root=str(self.root),
                                  file=["a.txt"], max_files=256, max_bytes=1024,
                                  reviewer="Reviewer", label="review", verdict="rejected",
                                  notes_file=str(self.notes), evidence=[], overwrite=True)
        actual_snapshot = MODULE.snapshot_file
        def snapshot_then_replace(*values):
            result = actual_snapshot(*values)
            os.replace(replacement, selected)
            return result
        with mock.patch.object(MODULE, "snapshot_file", side_effect=snapshot_then_replace):
            with self.assertRaises(MODULE.ReceiptError):
                MODULE.run(args)
        self.assertIn(selected.read_bytes(), (original, b"new bytes from a concurrent writer"))

    def test_case_alias_destination_stays_protected_during_replacement(self):
        import argparse
        selected = self.root / "Selected.txt"
        selected.write_bytes(b"original reviewed bytes")
        alias = self.root / "selected.txt"
        if not alias.exists():
            self.skipTest("filesystem distinguishes these case variants")
        replacement = self.base / "replacement.txt"
        replacement.write_bytes(b"new concurrent bytes")
        args = argparse.Namespace(command="author", receipt=str(alias), root=str(self.root),
                                  file=["Selected.txt"], max_files=256, max_bytes=1024,
                                  reviewer="Reviewer", label="review", verdict="rejected",
                                  notes_file=str(self.notes), evidence=[], overwrite=True)
        actual_snapshot = MODULE.snapshot_file
        def snapshot_then_replace(*values):
            result = actual_snapshot(*values)
            os.replace(replacement, selected)
            return result
        with mock.patch.object(MODULE, "snapshot_file", side_effect=snapshot_then_replace):
            with self.assertRaises(MODULE.ReceiptError):
                MODULE.run(args)
        self.assertIn(selected.read_bytes(), (b"original reviewed bytes", b"new concurrent bytes"))

    def test_duplicate_and_normalized_cli_selections_are_refused(self):
        for paths in (["a.txt", "a.txt"], ["./a.txt"], ["nested/../a.txt"],
                      ["nested//b.txt"], ["a.txt/"]):
            with self.subTest(paths=paths):
                self.run_cli("author", paths=paths, expected=2)
                self.assertFalse(self.receipt.exists())

    def test_selected_hardlinks_remain_two_explicit_path_obligations(self):
        os.link(self.root / "a.txt", self.root / "alias.txt")
        paths = ["a.txt", "alias.txt"]
        self.run_cli("author", paths=paths)
        result = self.run_cli("check", paths=paths)
        self.assertEqual(result["checked_files"], 2)
        (self.root / "alias.txt").unlink()
        result = self.run_cli("check", paths=paths, expected=3)
        self.assertEqual(result["findings"], [{"path": "alias.txt", "state": "missing", "fields": []}])


if __name__ == "__main__":
    unittest.main()
