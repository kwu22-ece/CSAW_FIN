"""Export visible project interactions from explicit local session snapshots."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from reproduce import digest, file_hash, json_bytes, publish, read_json, require

TOKEN = re.compile(r"(?:\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|AIza[A-Za-z0-9_-]{25,}|ya29\.[A-Za-z0-9._-]+|AKIA[A-Z0-9]{16})\b|-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----)")
ASSIGNMENT = re.compile(r"""(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|client_secret|password)\s*[=:]\s*["'])([^"'\s]{8,})(["'])""")
BEARER = re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{20,}=*")


def sanitize(text):
    text, tokens = TOKEN.subn("[REDACTED CREDENTIAL]", text)
    text, assignments = ASSIGNMENT.subn(r"\1[REDACTED CREDENTIAL]\3", text)
    text, bearers = BEARER.subn(r"\1[REDACTED CREDENTIAL]", text)
    return text, tokens + assignments + bearers


def sanitize_value(value):
    if isinstance(value, str):
        return sanitize(value)
    if isinstance(value, list):
        items = [sanitize_value(item) for item in value]
        return [item for item, _ in items], sum(count for _, count in items)
    if isinstance(value, dict):
        items = {key: sanitize_value(item) for key, item in value.items()}
        return {key: item for key, (item, _) in items.items()}, sum(count for _, count in items.values())
    return value, 0


def visible_record(record):
    if record.get("type") == "response_item":
        payload = record.get("payload", {})
        kind = payload.get("type")
        if kind == "message" and payload.get("role") in ("user", "assistant"):
            if payload.get("channel") in ("analysis", "summary"):
                return None
            return {"timestamp": record.get("timestamp"), "type": kind,
                    "role": payload["role"], "content": payload.get("content", [])}
        if kind in ("function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"):
            return {"timestamp": record.get("timestamp"), "type": kind,
                    **{k: v for k, v in payload.items() if k not in ("type", "encrypted_content")}}
    message = record.get("message", {})
    if record.get("type") in ("user", "assistant") and isinstance(message, dict):
        content = message.get("content", [])
        if isinstance(content, list):
            content = [part for part in content if part.get("type") in ("text", "tool_use", "tool_result")]
        return {"timestamp": record.get("timestamp"), "type": "message", "role": message.get("role", record["type"]),
                "content": content}
    return None


def export(plan, output):
    output.mkdir(parents=True, exist_ok=False)
    entries = []
    for item in read_json(plan):
        source = Path(item["path"])
        raw = source.read_bytes()
        if item.get("expected_sha256"):
            require(digest(raw) == item["expected_sha256"], f"Transcript snapshot hash changed: {source.name}")
        records = []
        models = set()
        malformed = 0
        redactions = 0
        for number, line in enumerate(raw.splitlines(), 1):
            try:
                record = json.loads(line)
            except ValueError:
                malformed += 1
                continue
            if record.get("type") == "turn_context":
                model = record.get("payload", {}).get("model")
                if model:
                    models.add(model)
            message = record.get("message")
            if isinstance(message, dict) and message.get("model"):
                models.add(message["model"])
            visible = visible_record(record)
            if visible is not None:
                cleaned, count = sanitize_value({"source_line": number, **visible})
                rendered = json.dumps(cleaned, ensure_ascii=False)
                redactions += count
                records.append(rendered)
        relative = item["phase"] + "/" + source.stem + ".interactions.jsonl"
        target = output / relative
        require(target.resolve().is_relative_to(output.resolve()), "Unsafe transcript destination")
        require(not target.exists(), f"Duplicate transcript destination {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = ("\n".join(records) + "\n").encode()
        publish(target, payload)
        entries.append({"phase": item["phase"], "file": relative, "source_file": source.name,
                        "raw_sha256": digest(raw), "raw_bytes": len(raw),
                        "export_sha256": digest(payload), "visible_records": len(records),
                        "runtime_models": sorted(models), "credential_redactions": redactions,
                        "malformed_records": malformed,
                        "source_size_stable_at_capture": source.stat().st_size == len(raw)})
    index = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(), "entries": entries,
        "scope": "Visible user/assistant messages and tool interactions from explicitly listed project sessions",
        "completeness": "Available local snapshots exported. Live sessions can gain later responses. Official sufficiency unverified.",
        "credential_handling": "Known token, private-key, authorization-header, and credential-assignment patterns redacted",
        "phase05_model_disclosure": "05B was requested as Astra; original recovered runtime metadata records gpt-6-luna. Quality review records gpt-6-astra.",
    }
    publish(output / "index.json", json_bytes(index))
    print(json.dumps({"sessions": len(entries), "visible_records": sum(e["visible_records"] for e in entries),
                      "credential_redactions": sum(e["credential_redactions"] for e in entries),
                      "malformed_records": sum(e["malformed_records"] for e in entries)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.plan, args.output)
