"""Private local recovery artifacts and audit storage for CML Tool."""

import datetime
import getpass
import hashlib
import json
import os
import time


RECOGNIZED_ARTIFACT_KINDS = {
    "cml-backup", "deployment-report", "association-delete-archive",
}
DEFAULT_RETENTION_DAYS = 90


def artifact_retention_days():
    """Return configured days; zero disables automatic artifact pruning."""
    raw = os.environ.get(
        "CML_ARTIFACT_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)).strip()
    if raw.lower() in {"0", "off", "false", "disabled", "none"}:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_RETENTION_DAYS
    return value if value > 0 else DEFAULT_RETENTION_DAYS


def prune_artifacts(directory, retention_days=None, now=None):
    """Delete expired tool artifacts only after recognizing their JSON kind."""
    days = artifact_retention_days() if retention_days is None else retention_days
    if not days or not os.path.isdir(directory):
        return []
    cutoff = (time.time() if now is None else now) - days * 86400
    removed = []
    for name in os.listdir(directory):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        try:
            if not os.path.isfile(path) or os.path.getmtime(path) >= cutoff:
                continue
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("kind") not in RECOGNIZED_ARTIFACT_KINDS:
                continue
            os.remove(path)
            removed.append(name)
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    return removed


class CrossProcessLock:
    """Non-blocking advisory file lock for one deployment target."""

    def __init__(self, directory, key):
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        self.path = os.path.join(directory, digest + ".lock")
        self.handle = None

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        self.handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                if self.handle.read(1) == b"":
                    self.handle.seek(0)
                    self.handle.write(b"\0")
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(
                    self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError):
            self.handle.close()
            self.handle = None
            return False

    def release(self):
        if not self.handle:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def safe_filename(name):
    """Return a cross-platform-safe filename segment with collision resistance."""
    raw = str(name or "")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    value = "".join(character if character in allowed else "_" for character in raw)
    value = value.strip("._")
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
    if (value.split(".", 1)[0] or "").upper() in reserved:
        value = "_" + value
    changed = value != raw or len(value) > 120
    value = value[:109] or "item"
    if changed:
        value += "__" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return value


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def artifact_stamp():
    return utc_now().strftime("%Y%m%dT%H%M%S.%fZ")


def sha256_text(content):
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def freeze_json_value(value):
    """Convert JSON collections into recursively hashable tuple identities."""
    if isinstance(value, list):
        return tuple(freeze_json_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted(
            (key, freeze_json_value(item)) for key, item in value.items()))
    return value


def write_json_artifact(directory, prefix, payload):
    """Atomically write a private JSON artifact and return public metadata."""
    os.makedirs(directory, mode=0o700, exist_ok=True)
    artifact_id = f"{artifact_stamp()}__{safe_filename(prefix)}.json"
    path = os.path.join(directory, artifact_id)
    temp_path = path + ".tmp"
    data = dict(payload)
    data.setdefault("createdAt", utc_now().isoformat())
    data.setdefault("operatingSystemUser", getpass.getuser())
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temp_path, 0o600)
    except OSError:
        pass
    os.replace(temp_path, path)
    prune_artifacts(directory)
    return {"id": artifact_id, "file": path, "createdAt": data["createdAt"]}


def read_json_artifact(directory, artifact_id):
    """Read one basename-only JSON artifact without path traversal."""
    safe_id = os.path.basename(artifact_id or "")
    if safe_id != artifact_id or not safe_id.endswith(".json"):
        return None, "Invalid artifact identifier."
    path = os.path.join(directory, safe_id)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except FileNotFoundError:
        return None, "The requested recovery artifact no longer exists."
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Could not read recovery artifact: {exc}"


def append_jsonl_audit(log_dir, audit_file, entry, lock):
    """Durably append one private JSON line under the caller's shared lock."""
    os.makedirs(log_dir, mode=0o700, exist_ok=True)
    payload = {
        "timestamp": utc_now().isoformat(),
        "operating_system_user": getpass.getuser(),
        **entry,
    }
    with lock:
        with open(audit_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(audit_file, 0o600)
        except OSError:
            pass
