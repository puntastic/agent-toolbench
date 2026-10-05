import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reporting


def fixture():
    rows = []
    for case in reporting.CASES:
        rows.append({"arm": "direct", "case": case, "passed": True,
                     "checks": dict.fromkeys(reporting.CHECKS, True),
                     "exit_code": 7 if case == "json-error" else 0,
                     "elapsed_seconds": 0.1, "capped": False,
                     "stdout": {"bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()},
                     "stderr": {"bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()}})
    return {"schema": "tool-interface-probe-v1", "source_sha256": "1" * 64,
            "codex_sha256": "2" * 64, "results": rows}


class ReportTests(unittest.TestCase):
    def test_valid_report_can_include_expected_nonzero_exit(self):
        self.assertEqual(reporting.validate(fixture()), [])

    def test_failed_check_is_not_misreported_as_invalid_report(self):
        report = fixture()
        report["results"][0]["checks"]["stdout"] = False
        report["results"][0]["passed"] = False
        self.assertEqual(reporting.validate(report), [])
        self.assertEqual(reporting.summarize(report)[0]["failed_cases"], ["argv"])

    def test_checker_catches_false_pass_and_missing_case(self):
        report = fixture()
        report["results"][0]["checks"]["stdout"] = False
        self.assertTrue(reporting.validate(report))
        report = fixture()
        report["results"].pop()
        self.assertTrue(reporting.validate(report))

    def test_checker_catches_duplicate_capture_cap_and_bad_digest(self):
        report = fixture()
        report["results"].append(copy.deepcopy(report["results"][0]))
        self.assertTrue(reporting.validate(report))
        report = fixture()
        report["results"][0]["capped"] = True
        self.assertTrue(reporting.validate(report))
        report = fixture()
        report["results"][0]["stdout"]["sha256"] = "not a digest"
        self.assertTrue(reporting.validate(report))

    def test_public_projection_preserves_evidence_but_drops_free_text(self):
        report = fixture()
        report["server"] = "private startup description"
        report["results"][0]["command"] = ["C:/Users/PRIVATE/program.exe"]
        report["results"][0]["payload_parse_error"] = "private diagnostic"
        raw = json.dumps(report).encode()
        projected = reporting.public_projection(raw, "fixture")
        self.assertNotIn("PRIVATE", json.dumps(projected))
        self.assertNotIn("private", json.dumps(projected))
        self.assertEqual(reporting.summarize(projected), reporting.summarize(report))
        self.assertEqual(projected["publication"]["source_record_sha256"], hashlib.sha256(raw).hexdigest())

    def test_execution_error_stays_visible_after_projection(self):
        report = fixture()
        report["results"][0] = {"arm": "direct", "case": "argv", "passed": False,
                                "error": "private execution diagnostic"}
        projected = reporting.public_projection(json.dumps(report).encode(), "fixture")
        self.assertTrue(projected["results"][0]["execution_error"])
        self.assertEqual(reporting.summarize(projected)[0]["execution_errors"], 1)

    def test_public_projection_cannot_launder_its_existing_source_binding(self):
        projected = reporting.public_projection(json.dumps(fixture()).encode(), "fixture")
        with self.assertRaises(ValueError):
            reporting.public_projection(json.dumps(projected).encode(), "again")

    def test_source_binding_is_checked_without_inventing_a_match(self):
        report = fixture()
        report.update(schema="tool-interface-probe-v2", selected_arms=["direct"],
                      source_sha256_start="3" * 64, source_hashes_match=False)
        self.assertEqual(reporting.validate(report), [])
        report["source_hashes_match"] = True
        self.assertTrue(reporting.validate(report))

    def test_malformed_selected_arms_are_reported_without_crashing(self):
        report = fixture()
        report["selected_arms"] = [{"bad": "arm"}]
        self.assertTrue(reporting.validate(report))

    def test_empty_stream_digest_must_match_empty_bytes(self):
        report = fixture()
        report["results"][0]["stdout"]["sha256"] = "0" * 64
        self.assertTrue(reporting.validate(report))

    def test_recorded_source_is_byte_bound(self):
        self.assertEqual(hashlib.sha256((ROOT / "provenance/recorded_probe.py").read_bytes()).hexdigest(),
                         "364dc6e0f465e0ab341e17acc837bd2fc05e40d7c0efa4e7f08a7ee7273c4234")

    def test_public_runner_matches_its_validation_receipt(self):
        report = reporting.load(ROOT / "results/harness-v2-validation.json")
        digest = hashlib.sha256((ROOT / "experiments/windows-execution/probe.py").read_bytes()).hexdigest()
        self.assertEqual(digest, report["source_sha256"])
        self.assertEqual(digest, report["source_sha256_start"])

    def test_published_records_and_counts(self):
        expected = {arm: (7 if arm in ("powershell", "bash") else 8) for arm in reporting.ARMS}
        for name in ("baseline", "candidate", "harness-v2-validation"):
            report = reporting.load(ROOT / f"results/{name}.json")
            self.assertEqual(reporting.validate(report), [])
            self.assertEqual({row["arm"]: row["passed"] for row in reporting.summarize(report)}, expected)

    def test_harness_argument_wrappers_keep_the_data_as_arguments(self):
        spec = importlib.util.spec_from_file_location("public_probe", ROOT / "experiments/windows-execution/probe.py")
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        arguments = ["program.exe", "two words", "", "$value", "literal|pipe"]
        self.assertEqual(probe.wrapped("direct", arguments, {}), arguments)
        wrapped = probe.wrapped("bash-literal", arguments, {"bash": "bash.exe"})
        self.assertEqual(wrapped[:3], ["bash.exe", "--noprofile", "--norc"])
        self.assertTrue(wrapped[-1].startswith("export MSYS2_ARG_CONV_EXCL='*'; "))


if __name__ == "__main__":
    unittest.main()
