"""Regression checks for private transcript export and release evidence integrity."""
import json
from pathlib import Path
import tempfile
import unittest

from release_transcripts import export, sanitize_value, visible_record
from reproduce import digest, json_bytes, verify_files
from release_package import selected_evidence, check_publication_bytes, verified_manifest_files


class ReleaseIntegrityTests(unittest.TestCase):
    def test_evidence_rejects_missing_modified_and_escaping_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "report.json"
            path.write_bytes(b"verified")
            hashes = {"report.json": digest(b"verified")}
            verify_files(root, hashes)
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed or missing"):
                verify_files(root, hashes)
            with self.assertRaises(ValueError):
                verify_files(root, {"absent.json": digest(b"verified")})
            with self.assertRaises(ValueError):
                verify_files(root, {"../outside.json": digest(b"verified")})

    def test_transcript_keeps_visible_tools_and_omits_reasoning(self):
        visible = {"type": "response_item", "payload": {"type": "function_call", "name": "test",
                                                        "arguments": '{"input": "value"}'}}
        self.assertEqual(visible_record(visible)["name"], "test")
        hidden = {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                                       "channel": "analysis", "content": "internal"}}
        self.assertIsNone(visible_record(hidden))
        claude = {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "internal"}, {"type": "text", "text": "visible"}]}}
        self.assertEqual(visible_record(claude)["content"], [{"type": "text", "text": "visible"}])

    def test_redaction_preserves_valid_json_and_records_count(self):
        synthetic = "sk-" + "q" * 24
        value = {"text": 'A token ' + synthetic + ' and password="' + "x" * 14 + '"',
                 "nested": [{"content": "visible"}]}
        clean, count = sanitize_value(value)
        self.assertGreaterEqual(count, 2)
        self.assertNotIn(synthetic, json.dumps(clean))
        self.assertEqual(json.loads(json.dumps(clean)), clean)
        with self.assertRaisesRegex(ValueError, "Credential pattern"):
            check_publication_bytes("unreviewed.txt", synthetic.encode())

    def test_export_verifies_source_and_indexes_models(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "session.jsonl"
            records = [{"type": "turn_context", "payload": {"model": "test-model"}},
                       {"type": "response_item", "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "run this test"}]}}]
            raw = b"".join(json_bytes(record).replace(b"\n", b"") + b"\n" for record in records)
            source.write_bytes(raw)
            plan = root / "plan.json"
            plan.write_bytes(json_bytes([{"phase": "test", "path": str(source), "expected_sha256": digest(raw)}]))
            export(plan, root / "export")
            index = json.loads((root / "export/index.json").read_text())
            self.assertEqual(index["entries"][0]["runtime_models"], ["test-model"])
            self.assertEqual(index["entries"][0]["visible_records"], 1)
            source.write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "snapshot hash changed"):
                export(plan, root / "changed-export")

    def test_old_candidate_receipt_cannot_authorize_new_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "selected-validation.json").write_bytes(json_bytes({
                "status": "passed", "selected_commit": "a" * 40}))
            with self.assertRaisesRegex(ValueError, "pinned candidate"):
                selected_evidence({"selected_commit": "b" * 40}, root)

    def test_remediation_manifest_requires_complete_hashed_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / "audit-remediation" / "report.md"
            report.parent.mkdir()
            report.write_bytes(b"verified remediation")
            manifest = root / "handoffs" / "phase-f" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes(json_bytes({"schema_version": 1, "phase": "F", "cycle": 2,
                "files": [{"path": "audit-remediation/report.md", "bytes": report.stat().st_size,
                           "sha256": digest(report.read_bytes())}]}))
            _, files = verified_manifest_files(root, "handoffs/phase-f/manifest.json")
            self.assertEqual(set(files), {"audit-remediation/report.md"})
            report.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed or missing"):
                verified_manifest_files(root, "handoffs/phase-f/manifest.json")


if __name__ == "__main__":
    unittest.main()
