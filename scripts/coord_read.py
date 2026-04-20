#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_cursor(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("line", 0))
    except Exception:
        return 0


def save_cursor(path: Path, line_no: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"line": line_no}, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def should_show(msg: dict, agent_id: str, topic: str | None) -> bool:
    if topic and msg.get("topic") != topic:
        return False
    targets = msg.get("to") or ["*"]
    if "*" in targets:
        return True
    return agent_id in targets


def format_line(line_no: int, msg: dict) -> str:
    bits = [
        f"[{line_no}]",
        msg.get("ts", "?"),
        msg.get("from", "?"),
        f"role={msg.get('role', 'agent')}",
        msg.get("type", "?"),
    ]
    topic = msg.get("topic")
    if topic:
        bits.append(f"topic={topic}")
    task_id = msg.get("task_id")
    if task_id:
        bits.append(f"task={task_id}")
    summary = msg.get("summary", "")
    lock = msg.get("lock")
    if lock:
        bits.append(f"lock={lock.get('action')}:{lock.get('key')}:{lock.get('status')}")
    attachment = msg.get("attachment")
    if attachment:
        bits.append(f"attachment={attachment.get('path')}")
    if summary:
        bits.append(f"summary={summary}")
    return " | ".join(bits)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read only new coordination messages for one agent.")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--messages", required=True, help="Path to messages.jsonl (required to prevent reading wrong team)")
    parser.add_argument("--state-dir", required=True, help="Path to state directory (required)")
    parser.add_argument("--topic")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--peek", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    messages_path = Path(args.messages)
    state_path = Path(args.state_dir) / f"{args.agent_id}.cursor.json"
    if not messages_path.exists():
        print("[]")
        return 0

    start_line = load_cursor(state_path)
    selected: list[tuple[int, dict]] = []

    with messages_path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            if line_no <= start_line:
                continue
            raw = raw.strip()
            if not raw:
                continue
            msg = json.loads(raw)
            if should_show(msg, args.agent_id, args.topic):
                selected.append((line_no, msg))

    if args.limit > 0:
        selected = selected[: args.limit]

    if args.json:
        print(json.dumps([{"line": line_no, "message": msg} for line_no, msg in selected], ensure_ascii=True, indent=2))
    else:
        for line_no, msg in selected:
            print(format_line(line_no, msg))

    if not args.peek and selected:
        save_cursor(state_path, selected[-1][0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
