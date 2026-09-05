"""Private local recovery artifacts and audit storage for CML Tool."""

import datetime
import getpass
import hashlib
import json
import os


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
