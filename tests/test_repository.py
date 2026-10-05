import hashlib
import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_patch_files_match_the_published_manifest(self):
        manifest = json.loads((ROOT / "patches/manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["patches"]:
            data = (ROOT / "patches" / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
            headers = re.findall(rb"^diff --git ", data, flags=re.MULTILINE)
            self.assertEqual(len(headers), entry["changed_files"])

    def test_relative_markdown_destinations_exist_and_stay_in_repository(self):
        for source in ROOT.rglob("*.md"):
            if "out" in source.relative_to(ROOT).parts or ".git" in source.relative_to(ROOT).parts:
                continue
            text = source.read_text(encoding="utf-8")
            for href in re.findall(r"\]\(([^\s)]+)\)", text):
                url = urlsplit(href)
                if url.scheme or url.netloc or not url.path:
                    continue
                target = (source.parent / unquote(url.path)).resolve()
                self.assertTrue(target.is_relative_to(ROOT), (source, href))
                self.assertTrue(target.exists(), (source, href))

    def test_qualification_counts_are_consistent_and_do_not_hide_failures(self):
        report = json.loads((ROOT / "results/qualification.json").read_text(encoding="utf-8"))
        for run in report["runs"]:
            self.assertEqual(run["passed"] + run["failures"], run["tests"])
            self.assertEqual(len(run["failed_tests"]) + run["omitted_failed_test_names"], run["failures"])
        self.assertEqual(report["runs"][0]["failures"], 204)
        self.assertEqual(report["runs"][2]["failures"], 2)


if __name__ == "__main__":
    unittest.main()
