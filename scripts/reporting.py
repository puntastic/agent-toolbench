"""Small, dependency-free checks and public projections for transport reports."""

import copy
import hashlib
import json
import math
import re
from pathlib import Path

ARMS = ("direct", "powershell", "powershell-utf8", "bash", "bash-literal", "nu")
CASES = ("argv", "json-error", "bad-json", "bytes", "flood", "stdin", "json-view", "windows")
CHECKS = {"exit", "stdout", "stderr", "complete"}
HASH = re.compile(r"[0-9a-f]{64}\Z")


def validate(report):
    """Check shape and consistency; a valid report can contain failed cases."""
    errors = []
    if not isinstance(report, dict):
        return ["report must be an object"]
    if report.get("schema") not in {"tool-interface-probe-v1", "tool-interface-probe-v2"}:
        errors.append("unknown report schema")
    for key in ("source_sha256", "codex_sha256"):
        if not isinstance(report.get(key), str) or not HASH.fullmatch(report[key]):
            errors.append(f"invalid {key}")
    if report.get("schema") == "tool-interface-probe-v2":
        start = report.get("source_sha256_start")
        if not isinstance(start, str) or not HASH.fullmatch(start):
            errors.append("invalid source_sha256_start")
        if report.get("source_hashes_match") is not (start == report.get("source_sha256")):
            errors.append("source hash comparison is inconsistent")
    rows = report.get("results")
    if not isinstance(rows, list) or not rows:
        return errors + ["results must be a nonempty list"]
    seen = set()
    by_arm = {}
    for index, row in enumerate(rows):
        prefix = f"result {index}"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        arm, case = row.get("arm"), row.get("case")
        if arm not in ARMS or case not in CASES:
            errors.append(f"{prefix} has an unknown arm or case")
            continue
        pair = (arm, case)
        if pair in seen:
            errors.append(f"duplicate {arm}/{case}")
        seen.add(pair)
        by_arm.setdefault(arm, set()).add(case)
        if type(row.get("passed")) is not bool:
            errors.append(f"{prefix} passed must be boolean")
        execution_error = bool(row.get("error") or row.get("execution_error"))
        if execution_error:
            if row.get("passed") is not False:
                errors.append(f"{prefix} execution error cannot pass")
            continue
        checks = row.get("checks")
        if not isinstance(checks, dict) or set(checks) != CHECKS or any(type(v) is not bool for v in checks.values()):
            errors.append(f"{prefix} must carry the four boolean checks")
        elif row.get("passed") is not all(checks.values()):
            errors.append(f"{prefix} passed disagrees with checks")
        if type(row.get("exit_code")) is not int:
            errors.append(f"{prefix} missing integer exit code")
        elapsed = row.get("elapsed_seconds")
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            errors.append(f"{prefix} invalid elapsed time")
        if type(row.get("capped")) is not bool:
            errors.append(f"{prefix} missing capture-cap state")
        elif isinstance(checks, dict) and checks.get("complete") is not (not row["capped"]):
            errors.append(f"{prefix} completeness disagrees with capture cap")
        for stream in ("stdout", "stderr"):
            value = row.get(stream)
            if not isinstance(value, dict) or type(value.get("bytes")) is not int or value["bytes"] < 0:
                errors.append(f"{prefix} invalid {stream} byte count")
            if not isinstance(value, dict) or not isinstance(value.get("sha256"), str) or not HASH.fullmatch(value["sha256"]):
                errors.append(f"{prefix} invalid {stream} digest")
            elif value.get("bytes") == 0 and value["sha256"] != hashlib.sha256(b"").hexdigest():
                errors.append(f"{prefix} empty {stream} has a nonempty-stream digest")
    for arm, cases in by_arm.items():
        if cases != set(CASES):
            errors.append(f"{arm} has an incomplete case set")
    selected = report.get("selected_arms")
    if selected is not None and (not isinstance(selected, list) or any(not isinstance(arm, str) for arm in selected)
                                 or len(selected) != len(set(selected)) or set(selected) != set(by_arm)):
        errors.append("selected_arms disagrees with observed arms")
    return errors


def summarize(report):
    errors = validate(report)
    if errors:
        raise ValueError("; ".join(errors))
    result = []
    for arm in ARMS:
        rows = [row for row in report["results"] if row["arm"] == arm]
        if not rows:
            continue
        result.append({
            "arm": arm,
            "passed": sum(row["passed"] for row in rows),
            "cases": len(rows),
            "failed_cases": [row["case"] for row in rows if not row["passed"]],
            "execution_errors": sum(bool(row.get("error") or row.get("execution_error")) for row in rows),
            "incomplete_captures": sum(bool(row.get("capped")) for row in rows),
        })
    return result


def public_projection(raw, label):
    report = json.loads(raw)
    if isinstance(report, dict) and "publication" in report:
        raise ValueError("Already a public projection; preserve its existing source-record binding.")
    errors = validate(report)
    if errors:
        raise ValueError("; ".join(errors))
    keep = ("schema", "source_sha256", "codex_sha256", "source_sha256_start", "source_hashes_match", "selected_arms")
    public = {key: copy.deepcopy(report[key]) for key in keep if key in report}
    public["scope"] = "Deterministic native-RPC transport fixtures; not model-generation, live-adoption, or general performance evidence."
    public["publication"] = {
        "projection_version": 1,
        "label": label,
        "source_record_sha256": hashlib.sha256(raw).hexdigest(),
        "omitted": ["launch commands", "startup descriptor", "free-form diagnostics"],
        "boundary": "Selected field removal, not a general privacy guarantee or proof of execution.",
    }
    keep_row = ("arm", "case", "exit_code", "elapsed_seconds", "stdout", "stderr", "capped", "checks", "passed")
    public["results"] = []
    for row in report["results"]:
        projected = {key: copy.deepcopy(row[key]) for key in keep_row if key in row}
        if row.get("error"):
            projected["execution_error"] = True
        if row.get("payload_parse_error"):
            projected["payload_parse_error_present"] = True
        public["results"].append(projected)
    if validate(public):
        raise ValueError("public projection changed report consistency")
    return public


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
