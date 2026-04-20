#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sanitize_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "lock"


def read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    return args.body or ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_attachment(base_dir: Path, msg_id: str, body: str, source_path: str | None) -> dict:
    ext = ".md"
    if source_path:
        suffix = Path(source_path).suffix
        if suffix:
            ext = suffix
    attachment_path = base_dir / f"{msg_id}{ext}"
    attachment_path.parent.mkdir(parents=True, exist_ok=True)
    attachment_path.write_text(body, encoding="utf-8")
    return {
        "path": str(attachment_path),
        "bytes": attachment_path.stat().st_size,
        "sha256": sha256_text(body),
    }


def manage_lock(locks_dir: Path, agent_id: str, key: str, action: str, summary: str, force: bool) -> dict:
    lock_path = locks_dir / f"{sanitize_key(key)}.json"
    locks_dir.mkdir(parents=True, exist_ok=True)
    if action == "none":
        return {}
    if action == "acquire":
        if lock_path.exists():
            current = json.loads(lock_path.read_text(encoding="utf-8"))
            if current.get("owner") != agent_id and not force:
                return {"key": key, "action": action, "status": "blocked", "owner": current.get("owner"), "path": str(lock_path)}
        data = {"owner": agent_id, "summary": summary, "updated_at": now_iso()}
        lock_path.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return {"key": key, "action": action, "status": "acquired", "path": str(lock_path)}
    if action == "release":
        if not lock_path.exists():
            return {"key": key, "action": action, "status": "released", "path": str(lock_path)}
        current = json.loads(lock_path.read_text(encoding="utf-8"))
        if current.get("owner") != agent_id and not force:
            return {"key": key, "action": action, "status": "blocked", "owner": current.get("owner"), "path": str(lock_path)}
        lock_path.unlink()
        return {"key": key, "action": action, "status": "released", "path": str(lock_path)}
    raise ValueError(f"Unknown lock action: {action}")


def is_duplicate_ack(messages_path: Path, agent_id: str, reply_to: str) -> bool:
    """Check if this agent already ACK'd the same reply_to target."""
    if not reply_to or not messages_path.exists():
        return False
    try:
        with messages_path.open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                msg = json.loads(raw)
                if msg.get("type") == "ack" and msg.get("from") == agent_id and msg.get("reply_to") == reply_to:
                    return True
    except Exception:
        return False
    return False


def normalize_dispatch(msg_type: str, dispatch: str, to_list: list[str]) -> tuple[str, list[str]]:
    # ack: 永远不唤醒
    if msg_type == "ack":
        return "none", ["user"]
    # challenge/decision/question/consensus: 必须唤醒，保底 all，但允许 targets
    if msg_type in {"challenge", "decision", "question", "consensus"}:
        if dispatch == "targets" and to_list != ["*"]:
            return "targets", to_list
        return "all", ["*"]
    # claim/intent/done: 状态声明，广播时降级为不唤醒
    if msg_type in {"claim", "intent", "done"} and dispatch == "all" and to_list == ["*"]:
        return "none", ["user"]
    if dispatch == "none" and to_list == ["*"]:
        return "none", ["user"]
    return dispatch, to_list


def load_messages(messages_path: Path) -> list[dict]:
    if not messages_path.exists():
        return []
    messages: list[dict] = []
    with messages_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                messages.append(json.loads(raw))
            except Exception:
                continue
    return messages


def matches_consensus_scope(consensus_entry: dict, candidate: dict) -> bool:
    consensus_task = consensus_entry.get("task_id")
    candidate_task = candidate.get("task_id")
    if consensus_task and candidate_task:
        return consensus_task == candidate_task
    if consensus_task and not candidate_task:
        return False
    consensus_topic = consensus_entry.get("topic")
    candidate_topic = candidate.get("topic")
    if consensus_topic and candidate_topic:
        return consensus_topic == candidate_topic
    if consensus_topic and not candidate_topic:
        return False
    return True


def get_active_consensus_window(messages_path: Path) -> tuple[dict | None, list[dict]]:
    timeline = load_messages(messages_path)
    if not timeline:
        return None, []

    latest_consensus_index = -1
    latest_consensus = None
    for index in range(len(timeline) - 1, -1, -1):
        if timeline[index].get("type") == "consensus":
            latest_consensus_index = index
            latest_consensus = timeline[index]
            break

    if latest_consensus is None:
        return None, []

    scoped_window = [
        entry
        for entry in timeline[latest_consensus_index + 1 :]
        if matches_consensus_scope(latest_consensus, entry)
    ]
    return latest_consensus, scoped_window


def should_skip_ack(messages_path: Path, agent_id: str, reply_to: str) -> tuple[bool, str]:
    """Check if an ACK should be skipped.
    - ACK decision: allowed (表态), only skip if duplicate or stale window
    - ACK conclusion: allowed, only skip if duplicate or stale window
    - ACK other: allowed, only skip if duplicate
    """
    timeline = load_messages(messages_path)
    if not timeline:
        return False, ""

    # Duplicate check: same agent already ACK'd same target
    for entry in timeline:
        if entry.get("type") == "ack" and entry.get("from") == agent_id and entry.get("reply_to") == reply_to:
            return True, f"duplicate ack for {reply_to}"

    # Stale window check: if reply_to target is from a superseded consensus window, skip
    # Find the latest consensus
    latest_consensus_index = -1
    for i in range(len(timeline) - 1, -1, -1):
        if timeline[i].get("type") == "consensus":
            latest_consensus_index = i
            break

    if latest_consensus_index >= 0:
        # Check if reply_to target exists in the current consensus window
        current_window_ids = set()
        for entry in timeline[latest_consensus_index + 1:]:
            entry_id = entry.get("id")
            if entry_id:
                current_window_ids.add(entry_id)

        # Also include entries before the consensus (non-consensus context)
        # The target must exist somewhere in the timeline
        target_exists = any(entry.get("id") == reply_to for entry in timeline)
        if not target_exists:
            return False, ""  # Target doesn't exist, let it through (will be harmless)

        # If target is before the latest consensus, it's from an old window
        target_in_current_window = reply_to in current_window_ids
        if not target_in_current_window:
            target_entry = next((e for e in timeline if e.get("id") == reply_to), None)
            if target_entry and target_entry.get("type") in ("decision", "conclusion"):
                return True, f"stale target {reply_to} from superseded consensus window"

    return False, ""


def find_decision_conflict(messages_path: Path, agent_id: str, supersede: str) -> dict | None:
    """Check if a new decision conflicts with an existing one.
    Returns None if no conflict, or a dict with conflict info.
    When supersede is provided and matches an existing decision, returns None (allowed).
    """
    _consensus_entry, scoped_window = get_active_consensus_window(messages_path)
    if not scoped_window:
        return None

    scoped_decisions = [entry for entry in scoped_window if entry.get("type") == "decision"]
    if not scoped_decisions:
        return None

    # Filter out already-superseded decisions
    superseded_ids = set()
    for entry in scoped_window:
        sid = entry.get("supersedes")
        if sid:
            superseded_ids.add(sid)
    active_decisions = [d for d in scoped_decisions if d.get("id") not in superseded_ids]
    if not active_decisions:
        return None

    latest_decision = active_decisions[-1]
    latest_decision_id = latest_decision.get("id", "")
    latest_decision_from = latest_decision.get("from", "")

    # If supersede is provided and matches the existing decision, allow
    if supersede and supersede == latest_decision_id:
        return None

    # Otherwise, conflict
    hint = f"use --supersede {latest_decision_id}" if latest_decision_from != agent_id else f"use --supersede {latest_decision_id} to update"
    return {
        "reason": f"existing decision {latest_decision_id} (from {latest_decision_from}). ACK or challenge it first; {hint}",
        "existing_decision_id": latest_decision_id,
        "existing_decision_from": latest_decision_from,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a coordination message with optional attachment and lock handling.")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--role", choices=["system", "user", "agent"], default="agent")
    parser.add_argument("--type", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--topic", default="general")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--to", default="*")
    parser.add_argument("--body")
    parser.add_argument("--body-file")
    parser.add_argument("--messages", required=True, help="Path to messages.jsonl (required to prevent writing to wrong team)")
    parser.add_argument("--attachments-dir", required=True, help="Path to attachments directory (required)")
    parser.add_argument("--locks-dir", required=True, help="Path to locks directory (required)")
    parser.add_argument("--max-inline-chars", type=int, default=400)
    parser.add_argument("--reply-to", default="")
    parser.add_argument("--lock-key", default="")
    parser.add_argument("--lock-action", choices=["none", "acquire", "release"], default="none")
    parser.add_argument("--force-lock", action="store_true")
    parser.add_argument("--supersede", default="", help="ID of existing decision to supersede")
    parser.add_argument("--dispatch", choices=["all", "targets", "none"], default="none")
    parser.add_argument("--images", default="", help="Comma-separated image file paths to attach for inline display")
    args = parser.parse_args()

    msg_id = f"msg-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    body = read_body(args)
    messages_path = Path(args.messages)
    messages_path.parent.mkdir(parents=True, exist_ok=True)

    attachment = None
    inline_body = body
    # Only create attachment file when --body-file is explicitly provided.
    # Regular messages keep body inline regardless of length.
    if body and args.body_file:
        attachment = write_attachment(Path(args.attachments_dir), msg_id, body, args.body_file)
        inline_body = body[: args.max_inline_chars].rstrip() + "..."

    # Auto-lock enforcement: claim auto-acquires a task lock, done auto-releases it
    lock_key = args.lock_key
    lock_action = args.lock_action
    if not lock_key and args.task_id:
        if args.type == "claim":
            lock_key = f"task-{args.task_id}"
            lock_action = "acquire"
        elif args.type == "done":
            lock_path = Path(args.locks_dir) / f"task-{args.task_id}.json"
            if lock_path.exists():
                lock_key = f"task-{args.task_id}"
                lock_action = "release"

    lock_info = manage_lock(Path(args.locks_dir), args.agent_id, lock_key, lock_action, args.summary, args.force_lock) if lock_key else {}

    to_list = [item.strip() for item in args.to.split(",") if item.strip()] or ["*"]
    dispatch, to_list = normalize_dispatch(args.type, args.dispatch, to_list)

    if args.type == "ack" and args.reply_to:
        skip_ack, skip_reason = should_skip_ack(messages_path, args.agent_id, args.reply_to)
        if skip_ack:
            skipped_msg = {
                "id": msg_id,
                "ts": now_iso(),
                "from": args.agent_id,
                "role": args.role,
                "to": to_list,
                "topic": args.topic,
                "task_id": args.task_id,
                "type": args.type,
                "summary": args.summary,
                "dispatch": dispatch,
                "reply_to": args.reply_to,
                "meta": {
                    "skipped": True,
                    "reason": skip_reason,
                },
            }
            print(json.dumps(skipped_msg, ensure_ascii=True, indent=2))
            return 0

    if args.type == "decision":
        decision_conflict = find_decision_conflict(messages_path, args.agent_id, args.supersede)
        if decision_conflict:
            conflict_msg = {
                "id": msg_id,
                "ts": now_iso(),
                "from": args.agent_id,
                "role": args.role,
                "to": to_list,
                "topic": args.topic,
                "task_id": args.task_id,
                "type": args.type,
                "summary": args.summary,
                "dispatch": dispatch,
                "meta": {
                    "decision_conflict": True,
                    **decision_conflict,
                },
            }
            print(json.dumps(conflict_msg, ensure_ascii=True, indent=2))
            return 4

    msg = {
        "id": msg_id,
        "ts": now_iso(),
        "from": args.agent_id,
        "role": args.role,
        "to": to_list,
        "topic": args.topic,
        "task_id": args.task_id,
        "type": args.type,
        "summary": args.summary,
        "dispatch": dispatch,
    }
    if inline_body:
        msg["body"] = inline_body
    if attachment:
        msg["attachment"] = attachment
    if args.reply_to:
        msg["reply_to"] = args.reply_to
    if args.supersede:
        msg["supersedes"] = args.supersede
    if lock_info:
        msg["lock"] = lock_info
    images = [p.strip() for p in args.images.split(",") if p.strip()] if args.images else []
    if images:
        msg["images"] = images

    with messages_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(msg, ensure_ascii=True) + "\n")

    print(json.dumps(msg, ensure_ascii=True, indent=2))
    if lock_info.get("status") == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
