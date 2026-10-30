"""Invented incidents and fake app-server peers only; never real feedback.

Windows storage fixtures inject privacy/fsync/locking checks internally: they
do not establish Windows ACL privacy or OS lock correctness, or create a
production bypass flag. Real POSIX checks run only on POSIX hosts.
"""
from contextlib import ExitStack, contextmanager
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "experiments/feedback-courier/feedback_courier.py"
SPEC = importlib.util.spec_from_file_location("feedback_courier", MODULE)
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


def incident():
    return {"incident_key": "synthetic:review-1", "kind": "guardian_denial", "reporter": "Synthetic Worker",
            "observed_at": "2026-10-31T01:02:03+10:00", "product": "Invented fixture product",
            "runtime": "synthetic-1", "operation": "Read a synthetic fixture",
            "observation": 'The invented review returned denial; literal café 🦋 "quotes" and `backticks` remain data.',
            "authority_or_expectation": "An invented fixture permission was present; this is not a real grant.",
            "source_limits": "Entirely synthetic test case, not a user incident or a real report.",
            "review_id": "synthetic-review-1"}


class FakeServer:
    mode = "accepted"
    instances = []
    before_feedback = None

    def __init__(self, executable, timeout):
        self.messages, self.closed = [], False
        type(self).instances.append(self)
        if self.mode == "spawn_failure":
            raise OSError("synthetic private detail must not escape")

    def write(self, message):
        if message.get("method") == "feedback/upload" and type(self).before_feedback:
            type(self).before_feedback(message)
        self.messages.append(copy.deepcopy(message))
        if message.get("method") == "feedback/upload" and self.mode == "write_failure":
            raise c.CourierError("pipe_closed", "Synthetic pipe closure")

    def receive(self, expected):
        if expected == "initialize":
            if self.mode == "init_refusal":
                raise c.CourierError("server_refusal", "Synthetic config/initialization refusal")
            return {"userAgent": "synthetic"}
        if self.mode in {"unknown", "config_refusal"}:
            raise c.CourierError("timeout" if self.mode == "unknown" else "server_refusal", "Synthetic post-dispatch outcome")
        if self.mode == "interrupt":
            raise KeyboardInterrupt()
        if self.mode == "bad_receipt":
            return {"ticketId": "not-the-supported-response"}
        if self.mode == "extended_receipt":
            return {"threadId": "opaque / synthetic-α", "promptHash": "provider-format-v2:aBc",
                    "extension": {"ignored": "not retained or executed"}}
        return {"threadId": "no-active-thread-synthetic", "promptHash": None}

    def close(self):
        self.closed = True
        return self.mode != "cleanup_failure"


class CourierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.ledger = self.directory / "private-ledger.json"
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        if os.name != "posix":
            self.stack.enter_context(patch.object(c, "_private_parent"))
            self.stack.enter_context(patch.object(c, "_sync_directory"))
            held = set()
            @contextmanager
            def synthetic_lock(path):
                if path in held:
                    raise c.CourierError("ledger_busy", "Synthetic lock is held")
                held.add(path)
                lock = path.with_name(path.name + ".lock")
                descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
                try:
                    yield
                finally:
                    os.close(descriptor)
                    held.remove(path)
            self.stack.enter_context(patch.object(c, "_ledger_lock", synthetic_lock))
        FakeServer.mode, FakeServer.instances, FakeServer.before_feedback = "accepted", [], None

    def send(self, value=None, **options):
        with patch.object(c, "OwnedServer", FakeServer):
            return c.send(value or incident(), self.ledger, Path(sys.executable), accept_runtime_metadata=True, **options)

    def stored(self):
        return json.loads(self.ledger.read_text(encoding="utf-8"))["incidents"][incident()["incident_key"]]

    def test_stdout_preparation_is_literal_and_never_opens_process_or_ledger(self):
        value = incident()
        with patch.object(c, "OwnedServer", side_effect=AssertionError("No process")), \
             patch.object(c, "Ledger", side_effect=AssertionError("No ledger")):
            result = c.prepare(value)
        self.assertTrue(result["ok"])
        self.assertEqual(set(result["feedback_params"]), {"classification", "reason", "includeLogs"})
        self.assertEqual(result["feedback_params"]["classification"], "safety_check")
        self.assertIs(result["feedback_params"]["includeLogs"], False)
        self.assertIn(value["observation"], result["fallback_text"])
        self.assertEqual(result["fallback_text"], result["feedback_params"]["reason"])
        self.assertFalse(result["dispatched_this_call"])
        self.assertEqual(c.parse_incident(c.encoded(value)), value)

    def test_strict_json_unknown_types_and_size(self):
        for raw in (b'{"kind":1,"kind":2}', b'{"x":NaN}', b'\xff', b'[]', b'x' * (c.MAX_INPUT + 1)):
            with self.subTest(raw=raw[:30]), self.assertRaises(c.CourierError):
                c.parse_incident(raw)
        for altered in ({**incident(), "extraLogFiles": []}, {**incident(), "observation": True},
                        {**incident(), "observed_at": "2026-10-31"}, {**incident(), "kind": "user_cancelled"},
                        {**incident(), "observation": "x" * 3001}):
            with self.subTest(fields=list(altered)), self.assertRaises(c.CourierError):
                c.validate_incident(altered)

    def test_optional_reported_impact_is_literal_bounded_and_never_invented(self):
        self.assertNotIn("Reported impact:", c.feedback_params(incident())["reason"])
        value = {**incident(), "reported_impact": "In this invented case, manual intervention interrupted a synthetic task."}
        reason = c.prepare(value)["fallback_text"]
        self.assertIn("Reported impact: " + value["reported_impact"], reason)
        self.assertTrue(reason.endswith("Please review how this action was assessed against the stated authorization or expectation, and provide a usable correction path if the decision was mistaken or unclear."))
        for impact in ("x" * 601, "new\nheader", "password=synthetic"):
            with self.subTest(impact=impact[:20]), self.assertRaises(c.CourierError):
                c.validate_incident({**incident(), "reported_impact": impact})

    def test_control_header_and_obvious_secret_guards_do_not_echo_input(self):
        for text in ("line\nbcc: nobody", "hello\rworld", "tab\ttext", "hidden\u202evalue",
                     "Authorization: invented", "sk-SYNTHETIC012345678901234", "password=synthetic", "Bearer SYNTHETIC0123456789"):
            with self.subTest(text=text), self.assertRaises(c.CourierError) as caught:
                c.validate_incident({**incident(), "observation": text})
            self.assertNotIn(text, str(caught.exception))

    def test_private_prepare_is_idempotent_and_conflict_preserves_old_bytes(self):
        first = c.prepare(incident(), self.ledger)
        before = self.ledger.read_bytes()
        second = c.prepare(incident(), self.ledger)
        self.assertEqual(first, second)
        self.assertEqual(self.ledger.read_bytes(), before)
        with self.assertRaisesRegex(c.CourierError, "different content"):
            c.prepare({**incident(), "observation": "Changed synthetic content"}, self.ledger)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_receipt_opaque_strings_and_extensions_do_not_invent_a_protocol(self):
        FakeServer.mode = "extended_receipt"
        result = self.send()
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["receipt"]["threadId"], "opaque / synthetic-α")
        self.assertEqual(result["receipt"]["promptHash"], "provider-format-v2:aBc")
        self.assertNotIn("extension", self.stored()["receipt"])
        self.assertEqual(self.send()["status"], "accepted")
        self.assertEqual(len(FakeServer.instances), 1)
        for value in ([], {}, {"threadId": 4}, {"threadId": "a\nb"}, {"threadId": "x" * 1025},
                      {"threadId": "synthetic", "promptHash": False}, {"threadId": "synthetic", "promptHash": "\u202e"}):
            with self.subTest(value=value), self.assertRaises(c.CourierError):
                c._receipt(value)

    def test_no_send_without_explicit_metadata_acceptance(self):
        with patch.object(c, "OwnedServer", side_effect=AssertionError("No process")):
            with self.assertRaises(c.CourierError) as caught:
                c.send(incident(), self.ledger, Path(sys.executable))
        self.assertEqual(caught.exception.code, "metadata_acceptance_required")
        self.assertFalse(self.ledger.exists())

    def test_public_sequence_and_durable_intent_precede_minimal_feedback(self):
        def before_feedback(message):
            state = self.stored()
            self.assertEqual(state["state"], "dispatch_intent")
            self.assertEqual(state["request_id"], message["id"])
            self.assertEqual(state["dispatch_attempts"], 1)
            self.assertEqual(message["params"], c.feedback_params(incident()))
        FakeServer.before_feedback = before_feedback
        result = self.send()
        server = FakeServer.instances[0]
        self.assertEqual([message["method"] for message in server.messages], ["initialize", "initialized", "feedback/upload"])
        self.assertEqual(server.messages[0]["params"], {"clientInfo": {"name": "agent-toolbench-feedback-courier", "version": c.VERSION}})
        self.assertEqual(result["status"], "accepted")
        self.assertTrue(server.closed)
        self.assertEqual(self.stored()["state"], "accepted")
        self.assertIn("not a support ticket", result["receipt"]["meaning"])

    def test_accepted_duplicate_and_content_conflict_never_spawn_again(self):
        self.send()
        with patch.object(c, "OwnedServer", side_effect=AssertionError("No duplicate process")):
            same = c.send(incident(), self.ledger, Path(sys.executable), accept_runtime_metadata=True)
            self.assertTrue(same["deduplicated"])
            self.assertFalse(same["dispatched_this_call"])
            with self.assertRaises(c.CourierError):
                c.send({**incident(), "operation": "Other operation"}, self.ledger, Path(sys.executable), accept_runtime_metadata=True)

    def test_unknown_refusal_bad_receipt_interrupt_and_write_failure_hold(self):
        for mode in ("unknown", "config_refusal", "bad_receipt", "interrupt", "write_failure"):
            with self.subTest(mode=mode):
                self.ledger = self.directory / (mode + ".json")
                FakeServer.mode = mode
                result = self.send()
                self.assertEqual(result["status"], "unconfirmed")
                self.assertTrue(result["review_required"])
                self.assertTrue(FakeServer.instances[-1].closed)
                with patch.object(c, "OwnedServer", side_effect=AssertionError("No uncertain retry")):
                    held = c.send(incident(), self.ledger, Path(sys.executable), accept_runtime_metadata=True)
                self.assertTrue(held["deduplicated"])
                self.assertFalse(held["dispatched_this_call"])
                self.assertEqual(self.stored()["dispatch_attempts"], 1)

    def test_pre_dispatch_failure_is_distinct_and_requires_another_explicit_send(self):
        FakeServer.mode = "init_refusal"
        result = self.send()
        self.assertEqual(result["status"], "pre_dispatch_failed")
        self.assertFalse(result["dispatched_this_call"])
        self.assertEqual(self.stored()["dispatch_attempts"], 0)
        self.assertNotIn("feedback/upload", [m["method"] for m in FakeServer.instances[-1].messages])
        FakeServer.mode = "accepted"
        self.assertEqual(self.send()["status"], "accepted")

    def test_active_lock_blocks_dispatch_but_inode_persists_after_release(self):
        lock = self.ledger.with_name(self.ledger.name + ".lock")
        with c.Ledger(self.ledger).locked(), patch.object(c, "OwnedServer", side_effect=AssertionError("No process")):
            inode = lock.stat().st_ino
            with self.assertRaises(c.CourierError) as caught:
                c.send(incident(), self.ledger, Path(sys.executable), accept_runtime_metadata=True)
        self.assertEqual(caught.exception.code, "ledger_busy")
        self.assertTrue(lock.exists())
        c.prepare(incident(), self.ledger)
        self.assertEqual(lock.stat().st_ino, inode)

    def test_crash_after_intent_before_feedback_remains_a_hold(self):
        c.prepare(incident(), self.ledger)
        original = c.Ledger.save
        def save_then_crash(ledger):
            original(ledger)
            if ledger.data["incidents"][incident()["incident_key"]]["state"] == "dispatch_intent":
                raise KeyboardInterrupt()
        with patch.object(c.Ledger, "save", save_then_crash):
            result = self.send()
        self.assertEqual(result["status"], "persistence_uncertain")
        self.assertFalse(result["dispatched_this_call"])
        self.assertEqual(self.stored()["state"], "dispatch_intent")
        self.assertTrue(FakeServer.instances[-1].closed)
        with patch.object(c, "OwnedServer", side_effect=AssertionError("No interrupted retry")):
            held = c.send(incident(), self.ledger, Path(sys.executable), accept_runtime_metadata=True)
        self.assertEqual(held["status"], "dispatch_intent")

    def test_failed_acceptance_persistence_keeps_durable_intent_not_retryable_success(self):
        c.prepare(incident(), self.ledger)
        original = c.Ledger.save
        def save(ledger):
            if ledger.data["incidents"][incident()["incident_key"]]["state"] == "accepted":
                raise OSError("synthetic disk failure")
            original(ledger)
        with patch.object(c.Ledger, "save", save):
            result = self.send()
        self.assertEqual(result["status"], "persistence_uncertain")
        self.assertIsNotNone(result["observed_receipt"])
        self.assertEqual(self.stored()["state"], "dispatch_intent")

    def test_interrupted_atomic_replace_keeps_old_ledger_and_cleans_temp_file(self):
        c.prepare(incident(), self.ledger)
        before = self.ledger.read_bytes()
        with c.Ledger(self.ledger).locked() as ledger:
            ledger.data["incidents"][incident()["incident_key"]]["state"] = "pre_dispatch_failed"
            with patch.object(c.os, "replace", side_effect=OSError("synthetic replace failure")):
                with self.assertRaises(OSError):
                    ledger.save()
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertFalse(list(self.directory.glob("*.tmp")))

    def test_cleanup_failure_does_not_undo_accepted_report_or_allow_retry(self):
        FakeServer.mode = "cleanup_failure"
        result = self.send()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "accepted")
        self.assertFalse(result["process_cleanup_confirmed"])
        self.assertEqual(self.send()["status"], "accepted")
        self.assertEqual(len(FakeServer.instances), 1)

    def test_ledger_tampering_cannot_add_an_attachment_or_change_digest(self):
        c.prepare(incident(), self.ledger)
        original = self.ledger.read_bytes()
        for target in ("params", "digest", "state"):
            value = json.loads(original)
            entry = value["incidents"][incident()["incident_key"]]
            if target == "params":
                entry["feedback_params"]["extraLogFiles"] = ["synthetic-file"]
            elif target == "digest":
                entry["content_digest"] = "0" * 64
            else:
                entry["state"] = "auto_retry"
            self.ledger.write_bytes(c.encoded(value))
            with patch.object(c, "OwnedServer", side_effect=AssertionError("No process")), self.assertRaises(c.CourierError):
                c.send(incident(), self.ledger, Path(sys.executable), accept_runtime_metadata=True)

    def test_ledger_wide_pacing_preserves_distinct_incident_without_spawning(self):
        with patch.object(c, "_now", return_value="2026-10-31T00:00:00+00:00"):
            self.assertEqual(self.send()["status"], "accepted")
        second = {**incident(), "incident_key": "synthetic:review-2", "review_id": "synthetic-review-2"}
        with patch.object(c, "_now", return_value="2026-10-31T00:01:00+00:00"), \
             patch.object(c, "OwnedServer", side_effect=AssertionError("Pacing must precede process creation")):
            deferred = c.send(second, self.ledger, Path(sys.executable), accept_runtime_metadata=True)
        self.assertEqual(deferred["status"], "deferred")
        self.assertFalse(deferred["dispatched_this_call"])
        self.assertEqual(deferred["next_eligible_at"], "2026-10-31T00:10:00+00:00")
        self.assertEqual(json.loads(self.ledger.read_bytes())["incidents"][second["incident_key"]]["state"], "prepared")
        with patch.object(c, "_now", return_value="2026-10-31T00:10:00+00:00"):
            self.assertEqual(self.send(second)["status"], "accepted")
        self.assertEqual(len(FakeServer.instances), 2)

    def test_unknown_holds_survive_interval_and_also_pace_distinct_events(self):
        FakeServer.mode = "unknown"
        with patch.object(c, "_now", return_value="2026-10-31T00:00:00+00:00"):
            self.send()
        second = {**incident(), "incident_key": "synthetic:review-2"}
        with patch.object(c, "_now", return_value="2026-10-31T00:01:00+00:00"):
            self.assertEqual(self.send(second)["status"], "deferred")
        with patch.object(c, "_now", return_value="2026-10-31T01:00:00+00:00"):
            held = self.send(min_interval=0)
        self.assertEqual(held["status"], "unconfirmed")
        self.assertFalse(held["dispatched_this_call"])
        self.assertEqual(len(FakeServer.instances), 1)

    def test_explicit_pacing_configuration_is_not_a_scheduler(self):
        with patch.object(c, "_now", return_value="2026-10-31T00:00:00+00:00"):
            self.send()
            second = {**incident(), "incident_key": "synthetic:review-2"}
            self.assertEqual(self.send(second, min_interval=0)["status"], "accepted")
        for interval in (-1, True, float("inf"), 604801):
            with self.subTest(interval=interval), self.assertRaises(c.CourierError):
                self.send({**incident(), "incident_key": "synthetic:review-3"}, min_interval=interval)


FAKE_PROCESS = r'''
import json, sys, time
mode = sys.argv[1]
for line in sys.stdin:
    message = json.loads(line)
    if message['method'] == 'initialize':
        if mode == 'flood':
            sys.stdout.write('x' * 300000); sys.stdout.flush(); time.sleep(5)
        elif mode == 'init_timeout':
            time.sleep(5)
        else:
            print(json.dumps({'id': message['id'], 'result': {}}), flush=True)
    elif message['method'] == 'feedback/upload':
        if mode == 'feedback_timeout':
            time.sleep(5)
        elif mode == 'refusal':
            print(json.dumps({'id': message['id'], 'error': {'code': -32600, 'message': 'synthetic refusal'}}), flush=True)
        else:
            print(json.dumps({'id': message['id'], 'result': {'threadId': 'no-active-thread-synthetic'}}), flush=True)
'''


class ProcessFixtureTests(unittest.TestCase):
    setUp = CourierTests.setUp
    stored = CourierTests.stored

    def fixture_send(self, mode, timeout=3):
        original = subprocess.Popen
        spawned = []
        def fixture(command, **options):
            self.assertEqual(command, [str(Path(sys.executable)), "app-server", "--listen", "stdio://"])
            self.assertNotIn("env", options)
            self.assertNotIn("shell", options)
            process = original([sys.executable, "-I", "-B", "-u", "-c", FAKE_PROCESS, mode], **options)
            spawned.append(process)
            return process
        started = time.monotonic()
        with patch.object(c.subprocess, "Popen", side_effect=fixture):
            result = c.send(incident(), self.ledger, Path(sys.executable), accept_runtime_metadata=True, timeout=timeout)
        self.assertEqual(len(spawned), 1)
        self.assertIsNotNone(spawned[0].poll())
        self.assertTrue(result["process_cleanup_confirmed"], result)
        self.assertLess(time.monotonic() - started, timeout + 6)
        return result

    def test_actual_fake_stdio_peer_accepts_and_is_reaped(self):
        result = self.fixture_send("accepted")
        self.assertEqual(result["status"], "accepted")

    def test_actual_fake_initialization_timeout_has_no_feedback_dispatch(self):
        result = self.fixture_send("init_timeout", timeout=1)
        self.assertEqual(result["status"], "pre_dispatch_failed")
        self.assertFalse(result["dispatched_this_call"])

    def test_actual_fake_output_flood_stops_and_is_reaped(self):
        result = self.fixture_send("flood")
        self.assertEqual(result["status"], "pre_dispatch_failed")
        self.assertEqual(result["error_code"], "output_limit")

    def test_actual_fake_post_dispatch_timeout_is_held_not_retried(self):
        result = self.fixture_send("feedback_timeout", timeout=1)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(self.stored()["dispatch_attempts"], 1)

    def test_interruption_at_constructor_handoff_reaps_created_fake_peer(self):
        calls = 0
        @contextmanager
        def interrupt_after_creation():
            nonlocal calls
            calls += 1
            selected = calls
            yield
            if selected == 1:
                raise KeyboardInterrupt()
        with patch.object(c, "_deferred_process_signals", interrupt_after_creation):
            result = self.fixture_send("accepted")
        self.assertEqual(result["status"], "pre_dispatch_failed")
        self.assertFalse(result["dispatched_this_call"])

    def test_interruption_after_os_creation_is_cleaned_inside_constructor(self):
        calls = 0
        @contextmanager
        def interrupt_after_creation():
            nonlocal calls
            calls += 1
            selected = calls
            yield
            if selected == 2:
                raise KeyboardInterrupt()
        with patch.object(c, "_deferred_process_signals", interrupt_after_creation):
            result = self.fixture_send("accepted")
        self.assertEqual(result["status"], "pre_dispatch_failed")
        self.assertFalse(result["dispatched_this_call"])


class PrivacyAndCliTests(unittest.TestCase):
    def test_portable_default_cli_prepares_stdout_without_creating_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            before = list(Path(temp).iterdir())
            result = subprocess.run([sys.executable, "-I", "-B", str(MODULE), "--input", "-"],
                                    input=c.encoded(incident()), capture_output=True, cwd=temp, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "prepared")
            self.assertEqual(list(Path(temp).iterdir()), before)

    @unittest.skipUnless(os.name == "posix", "Actual POSIX permission checks require a POSIX host")
    def test_actual_private_directory_and_file_modes_are_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            ledger = folder / "private.json"
            folder.chmod(0o700)
            c.prepare(incident(), ledger)
            self.assertEqual(stat.S_IMODE(ledger.stat().st_mode), 0o600)
            folder.chmod(0o755)
            with self.assertRaises(c.CourierError):
                c.prepare(incident(), ledger)
            folder.chmod(0o700)
            ledger.chmod(0o644)
            with self.assertRaises(c.CourierError):
                c.prepare(incident(), ledger)

    @unittest.skipUnless(os.name == "posix", "Actual POSIX lock validation requires a POSIX host")
    def test_actual_lock_rejects_nonprivate_or_aliased_inode(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            folder.chmod(0o700)
            ledger = folder / "private.json"
            lock = folder / "private.json.lock"
            c.prepare(incident(), ledger)
            lock.chmod(0o644)
            with self.assertRaises(c.CourierError):
                c.prepare(incident(), ledger)
            lock.chmod(0o600)
            duplicate = folder / "synthetic-hardlink"
            os.link(lock, duplicate)
            with self.assertRaises(c.CourierError):
                c.prepare(incident(), ledger)
            duplicate.unlink()
            lock.unlink()  # Deliberate fixture mutation, never a recovery tactic.
            lock.symlink_to(ledger)
            with self.assertRaises(c.CourierError):
                c.prepare(incident(), ledger)

    @unittest.skipUnless(os.name == "posix", "Actual process-death flock release requires POSIX")
    def test_process_death_releases_lock_without_releasing_unknown_incident(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            folder.chmod(0o700)
            ledger, marker = folder / "private.json", folder / "ready"
            script = """import importlib.util,json,pathlib,sys,time
spec=importlib.util.spec_from_file_location('courier',sys.argv[1])
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
value=c.parse_incident(sys.stdin.buffer.read())
with c.Ledger(sys.argv[2]).locked() as ledger:
    entry=ledger.entry(value)
    entry.update(state='dispatch_intent',dispatch_attempts=1,runtime_metadata_accepted=True,
                 request_id='feedback-'+'0'*32,dispatch_at=c._now())
    ledger.save()
    pathlib.Path(sys.argv[3]).write_text('synthetic lock owner ready')
    time.sleep(60)
"""
            process = subprocess.Popen([sys.executable, "-I", "-B", "-c", script, str(MODULE), str(ledger), str(marker)],
                                       stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                process.stdin.write(c.encoded(incident()))
                process.stdin.close()
                process.stdin = None
                until = time.monotonic() + 5
                while not marker.exists() and process.poll() is None and time.monotonic() < until:
                    time.sleep(0.02)
                self.assertTrue(marker.exists(), "Synthetic lock owner did not become ready")
                lock = ledger.with_name(ledger.name + ".lock")
                inode = lock.stat().st_ino
                with self.assertRaises(c.CourierError) as caught:
                    c.prepare(incident(), ledger)
                self.assertEqual(caught.exception.code, "ledger_busy")
                process.kill()
                _, stderr = process.communicate(timeout=5)
                self.assertEqual(stderr, b"")
                self.assertEqual(c.prepare(incident(), ledger)["status"], "dispatch_intent")
                self.assertEqual(c.prepare({**incident(), "incident_key": "synthetic:after-death"}, ledger)["status"], "prepared")
                self.assertEqual(lock.stat().st_ino, inode)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    @unittest.skipIf(os.name == "posix", "Windows refusal is a non-POSIX boundary")
    def test_windows_privacy_is_not_asserted_from_mode_bits(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(c.CourierError) as caught:
                c.prepare(incident(), Path(temp) / "private.json")
            self.assertEqual(caught.exception.code, "privacy_unverified")

    @unittest.skipUnless(os.name == "posix", "Actual SIGTERM/process-group cleanup requires POSIX")
    def test_sigterm_after_dispatch_reaps_fake_peer_and_preserves_unknown_hold(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            folder.chmod(0o700)
            ledger, source, peer, marker, received = (folder / name for name in ("ledger.json", "incident.json", "fake-codex", "peer.pid", "received"))
            source.write_bytes(c.encoded(incident()))
            peer.write_text("#!" + sys.executable + "\nimport pathlib,os\npathlib.Path(" + repr(str(marker)) + ").write_text(str(os.getpid()))\n"
                            + FAKE_PROCESS.replace("mode = sys.argv[1]", "mode = 'feedback_timeout'")
                            .replace("if mode == 'feedback_timeout':", "if mode == 'feedback_timeout':\n            pathlib.Path(" + repr(str(received)) + ").write_text('received')")
                            .replace("time.sleep(5)", "time.sleep(30)"), encoding="utf-8")
            peer.chmod(0o700)
            process = subprocess.Popen([sys.executable, "-I", "-B", str(MODULE), "send", "--input", str(source),
                                        "--ledger", str(ledger), "--codex", str(peer), "--accept-runtime-metadata", "--timeout-seconds", "30"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=folder)
            peer_pid = None
            try:
                until = time.monotonic() + 10
                while time.monotonic() < until:
                    if received.exists() and ledger.exists() and json.loads(ledger.read_bytes())["incidents"][incident()["incident_key"]]["state"] == "dispatch_intent":
                        peer_pid = int(marker.read_text())
                        break
                    time.sleep(0.02)
                self.assertIsNotNone(peer_pid, "Synthetic peer never reached dispatch")
                process.terminate()
                stdout, stderr = process.communicate(timeout=8)
                self.assertEqual(stderr, b"")
                result = json.loads(stdout)
                self.assertEqual(result["status"], "unconfirmed")
                self.assertEqual(result["error_code"], "interrupted")
                self.assertTrue(result["process_cleanup_confirmed"])
                self.assertEqual(json.loads(ledger.read_bytes())["incidents"][incident()["incident_key"]]["state"], "unconfirmed")
                with self.assertRaises(ProcessLookupError):
                    os.kill(peer_pid, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
                if peer_pid is not None:
                    try:
                        os.killpg(peer_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
