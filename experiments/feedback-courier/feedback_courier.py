"""Prepare caller-authored feedback; explicitly send once through normal app-server.

No incident detector, permission grant, redaction guarantee or support-ticket API.
Preparation without a ledger is portable and nonmutating. Ledger/send require a
verified private POSIX directory; Windows ACL privacy is not inferred from chmod.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import unicodedata
import uuid


VERSION = "0.1.0"
MAX_INPUT = 24576
MAX_LEDGER = 4 * 1024 * 1024
MAX_INCIDENTS = 256
MAX_OUTPUT = 256 * 1024
MAX_LINE = 65536
MAX_MESSAGES = 128
DEFAULT_MIN_INTERVAL = 600  # Caller-configurable project pacing, not a provider quota.
STATES = {"prepared", "pre_dispatch_failed", "dispatch_intent", "unconfirmed", "accepted"}
LIMITS = {"incident_key": 128, "kind": 32, "reporter": 80, "observed_at": 64,
          "product": 120, "runtime": 120, "operation": 256, "observation": 3000,
          "authority_or_expectation": 1200, "source_limits": 800, "review_id": 160, "call_id": 160,
          "reported_impact": 600}
REQUIRED = set(LIMITS) - {"review_id", "call_id", "reported_impact"}
TOKEN = re.compile(r"(?i)(?:\bsk-[a-z0-9_-]{12,}|\bAKIA[A-Z0-9]{16}\b|-----BEGIN[^-]*PRIVATE KEY|"
                   r"\b(?:bearer)\s+[a-z0-9._~+/-]{12,}|\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|"
                   r"refresh[_-]?token|password)\s*[:=]\s*\S+|\beyJ[a-z0-9_-]{12,}\.[a-z0-9_-]{12,}\.[a-z0-9_-]{12,})")
HEADER = re.compile(r"(?i)^\s*(?:to|cc|bcc|from|subject|reply-to|content-type|authorization|cookie|set-cookie)\s*:")
METADATA_NOTICE = ("No thread/log/file/tag parameters are sent, but the runtime may attach account/process/request metadata. "
                   "No absence of server association or retention is promised.")
AUTHORITY_NOTICE = "Metadata acceptance is not authority; the caller must already be authorised to submit this report."


class CourierError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CourierError("invalid_json", "Duplicate JSON fields are not accepted")
        result[key] = value
    return result


def parse_json(raw):
    def reject(_):
        raise CourierError("invalid_json", "Finite JSON values are required")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=reject)
    except (ValueError, UnicodeError, RecursionError):
        raise CourierError("invalid_json", "Use bounded UTF-8 JSON") from None


def validate_incident(value):
    if type(value) is not dict or not REQUIRED <= set(value) or set(value) - set(LIMITS):
        raise CourierError("invalid_incident", "Use exactly the documented incident fields")
    for key, text in value.items():
        if type(text) is not str or not text.strip() or len(text) > LIMITS[key]:
            raise CourierError("invalid_incident", "Incident fields must be nonempty bounded text")
        if any(unicodedata.category(char) in {"Cc", "Cs"} or char in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
               for char in text) or HEADER.search(text):
            raise CourierError("unsafe_text", "Control characters and header-like fields are not accepted")
        if TOKEN.search(text):
            raise CourierError("possible_secret", "Remove possible credentials before preparing feedback")
    if value["kind"] not in {"guardian_denial", "review_denial"}:
        raise CourierError("ineligible_incident", "Only an explicitly observed Guardian/action-review denial is eligible")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value["incident_key"]):
        raise CourierError("invalid_incident", "Use a stable bounded logical incident key")
    try:
        observed = datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise CourierError("invalid_incident", "observed_at needs an ISO8601 timestamp with timezone") from None
    if len(encoded(value)) > MAX_INPUT:
        raise CourierError("invalid_incident", "Incident exceeds its encoded input limit")
    return dict(value)


def parse_incident(raw):
    if len(raw) > MAX_INPUT:
        raise CourierError("invalid_incident", "Incident input exceeds 24576 bytes")
    return validate_incident(parse_json(raw))


def feedback_params(incident):
    lines = ["Product feedback: an observed action-review denial",
             "Reporter (caller-supplied designation): " + incident["reporter"],
             "Observed: " + incident["observed_at"],
             "Product/runtime (reported): " + incident["product"] + " / " + incident["runtime"],
             "Affected operation: " + incident["operation"],
             "Observation: " + incident["observation"]]
    if "reported_impact" in incident:
        lines.append("Reported impact: " + incident["reported_impact"])
    lines.extend(["Already-given authority or expected result: " + incident["authority_or_expectation"],
                  "Source and attribution limits: " + incident["source_limits"]])
    for key in ("review_id", "call_id"):
        if key in incident:
            lines.append(key + " (reported): " + incident[key])
    lines.append("Please review how this action was assessed against the stated authorization or expectation, and provide a usable correction path if the decision was mistaken or unclear.")
    return {"classification": "safety_check", "reason": "\n".join(lines), "includeLogs": False}


def content_digest(incident):
    return hashlib.sha256(encoded(incident)).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _private_parent(path):
    if os.name != "posix":
        raise CourierError("privacy_unverified", "Ledger/send require verified POSIX ownership/modes; Windows ACL privacy is unverified")
    if not path.is_absolute() or ".." in path.parts:
        raise CourierError("private_path_required", "Use an absolute private ledger path without traversal")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise CourierError("private_path_required", "Ledger paths must not traverse symlinks")
    info = path.parent.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise CourierError("private_path_required", "Use an existing owner-only POSIX ledger directory")
    repository = Path(__file__).resolve().parents[2]
    if (repository / ".git").exists() and path.is_relative_to(repository):
        raise CourierError("private_path_required", "Incident ledgers must stay outside the source repository")
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise CourierError("private_path_required", "Existing ledger ownership or privacy is not acceptable")


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def _ledger_lock(path):
    # A persistent inode prevents split locks. The OS releases flock on owner
    # death; per-incident durable intent, not an abandoned lockfile, holds doubt.
    import fcntl
    lock = path.with_name(path.name + ".lock")
    if lock.is_symlink():
        raise CourierError("private_path_required", "The ledger lock must not be a symlink")
    flags = os.O_RDWR | os.O_CREAT | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(lock, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_nlink != 1):
            raise CourierError("private_path_required", "The ledger lock must be an owner-only regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CourierError("ledger_busy", "Another process owns this ledger; no dispatch was attempted") from None
        current = lock.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise CourierError("private_path_required", "The ledger lock changed during acquisition")
        yield
    finally:
        os.close(descriptor)  # Never unlink the shared lock inode, even on error.


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        self.data = None

    @contextmanager
    def locked(self):
        _private_parent(self.path)
        with _ledger_lock(self.path):
            self.data = {"schema": "feedback-courier-ledger-v1", "incidents": {}}
            if self.path.exists():
                with self.path.open("rb") as stream:
                    raw = stream.read(MAX_LEDGER + 1)
                if len(raw) > MAX_LEDGER:
                    raise CourierError("ledger_invalid", "Ledger exceeds its bounded size")
                self.data = parse_json(raw)
            if (type(self.data) is not dict or set(self.data) != {"schema", "incidents"}
                    or self.data["schema"] != "feedback-courier-ledger-v1" or type(self.data["incidents"]) is not dict
                    or len(self.data["incidents"]) > MAX_INCIDENTS):
                raise CourierError("ledger_invalid", "Ledger shape is unsupported; no automatic migration")
            for key, entry in self.data["incidents"].items():
                incident = validate_incident(entry.get("incident")) if type(entry) is dict else None
                if (incident is None or key != incident["incident_key"] or entry.get("state") not in STATES
                        or entry.get("content_digest") != content_digest(incident)
                        or entry.get("feedback_params") != feedback_params(incident)
                        or type(entry.get("dispatch_attempts")) is not int or not 0 <= entry["dispatch_attempts"] <= 1000
                        or set(entry) - {"incident", "content_digest", "feedback_params", "state", "created_at", "updated_at",
                                         "dispatch_attempts", "request_id", "runtime_metadata_accepted", "receipt", "last_error_code",
                                         "process_cleanup_confirmed", "dispatch_at"}):
                    raise CourierError("ledger_invalid", "Ledger identity, content or prepared request differs")
                if entry["state"] in {"dispatch_intent", "unconfirmed", "accepted"} and (
                        entry["dispatch_attempts"] < 1 or entry.get("runtime_metadata_accepted") is not True
                        or type(entry.get("request_id")) is not str or not re.fullmatch(r"feedback-[0-9a-f]{32}", entry["request_id"])):
                    raise CourierError("ledger_invalid", "Dispatch state lacks its bound intent")
                if entry["state"] in {"dispatch_intent", "unconfirmed", "accepted"}:
                    _ledger_time(entry.get("dispatch_at"))
                if entry["state"] == "accepted":
                    receipt = entry.get("receipt")
                    if (type(receipt) is not dict or set(receipt) != {"threadId", "promptHash", "meaning"}
                            or receipt != _receipt({key: receipt[key] for key in ("threadId", "promptHash")})
                            or type(entry.get("process_cleanup_confirmed")) is not bool):
                        raise CourierError("ledger_invalid", "Accepted state lacks its supported receipt and cleanup observation")
            yield self

    def entry(self, incident):
        key, sha = incident["incident_key"], content_digest(incident)
        entry = self.data["incidents"].get(key)
        if entry is not None:
            if entry["content_digest"] != sha:
                raise CourierError("incident_conflict", "The incident key is already bound to different content")
            return entry
        if len(self.data["incidents"]) >= MAX_INCIDENTS:
            raise CourierError("ledger_full", "Ledger needs deliberate upkeep; no incident was discarded")
        entry = {"incident": incident, "content_digest": sha, "feedback_params": feedback_params(incident),
                 "state": "prepared", "created_at": _now(), "updated_at": _now(), "dispatch_attempts": 0}
        self.data["incidents"][key] = entry
        self.save()
        return entry

    def save(self):
        data = encoded(self.data)
        if len(data) > MAX_LEDGER:
            raise CourierError("ledger_full", "Ledger exceeds its bounded size; no automatic pruning")
        temporary = self.path.with_name("." + self.path.name + "." + uuid.uuid4().hex + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            _sync_directory(self.path.parent)
        finally:
            if temporary.exists():
                temporary.unlink()


def _prepared(incident, entry=None):
    params = feedback_params(incident) if entry is None else entry["feedback_params"]
    return {"ok": True, "action": "prepare", "status": "prepared" if entry is None else entry["state"],
            "incident_key": incident["incident_key"], "content_digest": content_digest(incident),
            "feedback_params": params, "fallback_text": params["reason"], "dispatched_this_call": False,
            "metadata_notice": METADATA_NOTICE, "authority_notice": AUTHORITY_NOTICE,
            "redaction_notice": "These checks catch only selected obvious patterns; the caller owns sanitisation."}


def prepare(incident, ledger_path=None):
    incident = validate_incident(incident)
    if ledger_path is None:
        return _prepared(incident)
    with Ledger(ledger_path).locked() as ledger:
        return _prepared(incident, ledger.entry(incident))


@contextmanager
def _deferred_process_signals():
    """Do not lose a newly created child before Popen returns its handle."""
    previous, pending = {}, []
    try:
        if os.name == "posix":
            for selected in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
                previous[selected] = signal.getsignal(selected)
                signal.signal(selected, lambda signum, frame: pending.append(signum))
        yield
    finally:
        for selected, handler in previous.items():
            signal.signal(selected, handler)
    if pending:
        handler = previous[pending[0]]
        if callable(handler):
            handler(pending[0], None)
        raise KeyboardInterrupt()


class OwnedServer:
    """One disposable process, fixed public protocol, bounded pipes and lifetime."""
    def __init__(self, executable, timeout):
        self.deadline = time.monotonic() + timeout
        self.lines, self.failure = queue.Queue(MAX_MESSAGES), threading.Event()
        self.count, self.messages, self.counter_lock = 0, 0, threading.Lock()
        self.workers = []
        options = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NO_WINDOW}
        self.process = None
        try:
            with _deferred_process_signals():
                self.process = subprocess.Popen([str(executable), "app-server", "--listen", "stdio://"],
                                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                bufsize=0, close_fds=True, **options)
            for stream, stdout in ((self.process.stdout, True), (self.process.stderr, False)):
                worker = threading.Thread(target=self._pump, args=(stream, stdout), daemon=True)
                worker.start()
                self.workers.append(worker)
        except BaseException:
            if self.process is not None:
                self.close()
            raise

    def _pump(self, stream, stdout):
        try:
            while True:
                data = stream.readline(MAX_LINE + 1) if stdout else stream.read(4096)
                if not data:
                    if stdout:
                        self.lines.put_nowait(None)
                    return
                with self.counter_lock:
                    self.count += len(data)
                    self.messages += int(stdout)
                    if self.count > MAX_OUTPUT or self.messages > MAX_MESSAGES or stdout and len(data) > MAX_LINE:
                        self.failure.set()
                        return
                if stdout:
                    self.lines.put_nowait(data)
        except (OSError, ValueError, queue.Full):
            self.failure.set()

    def _remaining(self):
        if self.failure.is_set():
            raise CourierError("output_limit", "Owned process output was invalid or exceeded its limit")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise CourierError("timeout", "Owned process exceeded the operation deadline")
        return min(remaining, 0.05)

    def write(self, message):
        completed = queue.Queue(1)
        def writer():
            try:
                data = encoded(message) + b"\n"
                view = memoryview(data)
                while view:
                    count = self.process.stdin.write(view)
                    if not count:
                        raise OSError()
                    view = view[count:]
                self.process.stdin.flush()
                completed.put(True)
            except (OSError, ValueError):
                completed.put(False)
        worker = threading.Thread(target=writer, daemon=True)
        self.workers.append(worker)
        worker.start()
        while True:
            try:
                if not completed.get(timeout=self._remaining()):
                    raise CourierError("pipe_closed", "Owned process input closed")
                return
            except queue.Empty:
                pass

    def receive(self, expected_id):
        while True:
            try:
                raw = self.lines.get(timeout=self._remaining())
            except queue.Empty:
                continue
            if raw is None:
                raise CourierError("process_exited", "Owned process ended before the expected response")
            response = parse_json(raw)
            if type(response) is not dict:
                raise CourierError("invalid_response", "Expected a JSON-RPC object")
            if "id" not in response and type(response.get("method")) is str:
                continue  # Notifications are not new incidents or permission to call anything.
            if response.get("id") != expected_id or ("result" in response) == ("error" in response):
                raise CourierError("invalid_response", "Response identity or result shape differs")
            if "error" in response:
                raise CourierError("server_refusal", "The runtime returned a JSON-RPC error; no error body was copied")
            if type(response["result"]) is not dict:
                raise CourierError("invalid_response", "Expected an object result")
            return response["result"]

    def close(self):
        clean = True
        for force in (False, True):
            try:
                if os.name == "posix":
                    os.killpg(self.process.pid, signal.SIGKILL if force else signal.SIGTERM)
                elif self.process.poll() is None:
                    self.process.kill() if force else self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=2)
                break
            except subprocess.TimeoutExpired:
                if force:
                    clean = False
        if os.name == "posix":
            # A child may keep the private process group alive after the leader
            # exits. This group was created only for this disposable invocation.
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            try:
                stream.close()
            except (OSError, ValueError):
                clean = False
        for worker in self.workers:
            worker.join(timeout=0.5)
        return self.process.poll() is not None and not any(worker.is_alive() for worker in self.workers) and clean


def _receipt(result):
    def opaque(value):
        return (type(value) is str and len(value) <= 1024
                and not any(unicodedata.category(char) in {"Cc", "Cs"}
                            or char in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069" for char in value))
    # These are provider-reported opaque strings, not a locally invented ID/hash
    # grammar. Unconsumed response extensions are neither persisted nor acted on.
    if (type(result) is not dict or not opaque(result.get("threadId"))
            or result.get("promptHash") is not None and not opaque(result["promptHash"])):
        raise CourierError("invalid_receipt", "Feedback response did not match the supported receipt shape")
    return {"threadId": result["threadId"], "promptHash": result.get("promptHash"),
            "meaning": "Feedback RPC accepted; not a support ticket, durable-storage proof or human-review acknowledgment."}


def _ledger_time(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError()
        return result
    except (TypeError, ValueError):
        raise CourierError("ledger_invalid", "A dispatch timestamp is invalid") from None


def _next_eligible(ledger, interval):
    dispatched = [_ledger_time(entry["dispatch_at"]) for entry in ledger.data["incidents"].values() if "dispatch_at" in entry]
    if not dispatched:
        return None
    try:
        eligible = max(dispatched) + timedelta(seconds=interval)
    except OverflowError:
        raise CourierError("ledger_invalid", "Dispatch time is outside the supported range") from None
    return eligible.isoformat() if _ledger_time(_now()) < eligible else None


@contextmanager
def _termination_scope():
    # A catchable termination must unwind the same cleanup/unknown-outcome path
    # as Ctrl-C. Abrupt process/host death is not a cleanup guarantee.
    previous = {}
    try:
        if os.name == "posix":
            if threading.current_thread() is not threading.main_thread():
                raise CourierError("unsupported_send_context", "POSIX send must own the main-thread signal lifetime")
            def interrupted(signum, frame):
                for selected in previous:
                    signal.signal(selected, signal.SIG_IGN)
                raise KeyboardInterrupt()
            for selected in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
                previous[selected] = signal.getsignal(selected)
                signal.signal(selected, interrupted)
        yield
    finally:
        for selected, handler in previous.items():
            signal.signal(selected, handler)


def send(incident, ledger_path, executable, *, accept_runtime_metadata=False, timeout=45, min_interval=DEFAULT_MIN_INTERVAL):
    incident = validate_incident(incident)
    if accept_runtime_metadata is not True:
        raise CourierError("metadata_acceptance_required", METADATA_NOTICE + " " + AUTHORITY_NOTICE)
    if type(timeout) not in (int, float) or not 1 <= timeout <= 120:
        raise CourierError("invalid_timeout", "Use an operation deadline from1 to120 seconds")
    if type(min_interval) is not int or not 0 <= min_interval <= 604800:
        raise CourierError("invalid_interval", "Use project pacing from0 to604800 seconds within actual recipient limits")
    executable = Path(executable)
    if not executable.is_absolute() or not executable.is_file():
        raise CourierError("invalid_executable", "Select an existing absolute Codex executable")
    with _termination_scope(), Ledger(ledger_path).locked() as ledger:
        entry = ledger.entry(incident)
        if entry["state"] in {"accepted", "dispatch_intent", "unconfirmed"}:
            settled = entry["state"] == "accepted" and entry.get("process_cleanup_confirmed") is True
            return {"ok": settled, "action": "send", "status": entry["state"],
                    "deduplicated": True, "dispatched_this_call": False,
                    "review_required": not settled, "receipt": entry.get("receipt")}
        eligible = _next_eligible(ledger, min_interval)
        if eligible is not None:
            return {"ok": True, "action": "send", "status": "deferred", "ledger_state": entry["state"],
                    "dispatched_this_call": False, "next_eligible_at": eligible,
                    "min_interval_seconds": min_interval, "policy": "Project pacing, not a provider quota; no automatic retry or drain."}
        server, dispatched, receipt, error = None, False, None, None
        try:
            # Cover the constructor-to-caller handoff too: no signal may strand
            # a completed server object before this owner receives its handle.
            with _deferred_process_signals():
                server = OwnedServer(executable, timeout)
            server.write({"jsonrpc": "2.0", "id": "initialize", "method": "initialize",
                          "params": {"clientInfo": {"name": "agent-toolbench-feedback-courier", "version": VERSION}}})
            server.receive("initialize")
            server.write({"jsonrpc": "2.0", "method": "initialized"})
            request_id = "feedback-" + uuid.uuid4().hex
            entry.update(state="dispatch_intent", updated_at=_now(), request_id=request_id,
                         dispatch_attempts=entry["dispatch_attempts"] + 1, runtime_metadata_accepted=True, dispatch_at=_now())
            ledger.save()  # A crash from here forward holds, never silently re-dispatches.
            dispatched = True
            server.write({"jsonrpc": "2.0", "id": request_id, "method": "feedback/upload", "params": entry["feedback_params"]})
            receipt = _receipt(server.receive(request_id))
        except (CourierError, OSError, KeyboardInterrupt) as failure:
            error = failure.code if isinstance(failure, CourierError) else "interrupted" if isinstance(failure, KeyboardInterrupt) else "local_io_failure"
        finally:
            try:
                cleaned = server.close() if server is not None else True
            except KeyboardInterrupt:
                # The installed handler ignores repeat TERM/HUP after the first
                # signal, so finish the owned cleanup even if it arrived here.
                cleaned = server.close() if server is not None else True
                error = error or "interrupted"
        # If saving the intent itself failed, do not overwrite a possibly durable
        # intent with a retryable state. No feedback frame has been sent here.
        if not dispatched and entry["state"] == "dispatch_intent":
            return {"ok": False, "action": "send", "status": "persistence_uncertain", "dispatched_this_call": False,
                    "review_required": True, "error_code": error, "process_cleanup_confirmed": cleaned}
        entry.update(state="accepted" if receipt else "unconfirmed" if dispatched else "pre_dispatch_failed", updated_at=_now(),
                     process_cleanup_confirmed=cleaned)
        if receipt:
            entry["receipt"] = receipt
        if error:
            entry["last_error_code"] = error
        try:
            ledger.save()
        except (CourierError, OSError):
            return {"ok": False, "action": "send", "status": "persistence_uncertain", "dispatched_this_call": dispatched,
                    "review_required": True, "observed_receipt": receipt, "process_cleanup_confirmed": cleaned}
        return {"ok": receipt is not None and cleaned, "action": "send", "status": entry["state"],
                "dispatched_this_call": dispatched, "review_required": receipt is None or not cleaned,
                "error_code": error, "receipt": receipt, "process_cleanup_confirmed": cleaned}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("prepare", "send"), default="prepare")
    parser.add_argument("--input", required=True, help="Explicit sanitised incident JSON file, or - for stdin")
    parser.add_argument("--ledger", help="Explicit private POSIX ledger outside this repository")
    parser.add_argument("--codex", help="Operator-selected absolute Codex executable; used only by send")
    parser.add_argument("--accept-runtime-metadata", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=45)
    parser.add_argument("--min-interval-seconds", type=int, default=DEFAULT_MIN_INTERVAL,
                        help="Ledger-wide project pacing, not a provider quota; no automatic drain")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        else:
            with Path(args.input).open("rb") as source:
                raw = source.read(MAX_INPUT + 1)
        incident = parse_incident(raw)
        if args.action == "prepare":
            result = prepare(incident, args.ledger)
        else:
            if args.ledger is None or args.codex is None:
                raise CourierError("missing_send_inputs", "send requires an explicit private ledger and Codex executable")
            result = send(incident, args.ledger, args.codex, accept_runtime_metadata=args.accept_runtime_metadata,
                          timeout=args.timeout_seconds, min_interval=args.min_interval_seconds)
    except (CourierError, OSError, KeyboardInterrupt) as error:
        result = {"ok": False, "error": {"code": error.code if isinstance(error, CourierError) else "interrupted" if isinstance(error, KeyboardInterrupt) else "local_io_failure",
                                          "message": str(error) if isinstance(error, CourierError) else "Local operation failed or was interrupted; inspect any ledger before another send"}}
    sys.stdout.buffer.write(encoded(result) + b"\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
