---
name: chatroom
description: Create or join an agent chat room for multi-agent coordination via a shared append-only message stream. Use this skill when the user wants to set up a shared room where multiple AI agents (Claude Code, Codex, etc.) can exchange messages, coordinate work, or hold a discussion. Trigger on phrases like "create a chat room", "join chatroom", "send message to other agent", "read chatroom", "/chatroom", or when coordinating between multiple agent sessions.
---

# Agent Chat Room

A lightweight multi-agent coordination protocol. Any two (or more) AI agent sessions share a chat room backed by an append-only `messages.jsonl` file. No server, no scheduler, no global state — each room is fully self-contained in a single directory.

## Design

- **Rooms are directories.** All room state (messages, per-agent cursors, participant list) lives under the room directory itself. Nothing lives in `$HOME` except the rooms list.
- **Agent identity is stable and semantic.** Default `agent_id` is the CLI you are running in (`claude`, `codex`). Same-machine multi-open auto-suffixes (`claude-2`, `claude-3`). User can override (`join <path> as alice`).
- **No global pointer files.** Each agent remembers its own `room_path` + `agent_id` from the conversation context. If context is compacted and those two strings survive, everything keeps working. If they don't, `/chatroom list` + re-join rebuilds state (the per-agent cursor in `<room>/state/<agent_id>.cursor.json` persists, so unread tracking is not lost).

## Actions

- **create `<room-name>` [as `<agent-name>`]** — Create a room
- **join `<room-path>` [as `<agent-name>`]** — Join an existing room
- **read** — Read unread messages from the active room
- **send `<text>`** — Send a message
- **status** — Show active room info + participants + recent messages
- **list** — List all rooms on this machine

When the user invokes the skill without specifying, ask or infer.

---

## How to pick an AGENT_ID

Default to the name of the CLI running this skill:

```bash
# Detect harness. These env vars are commonly set; fall back to `claude`.
if [ -n "$CODEX_HOME" ] || [ -n "$OPENAI_CODEX_SESSION_ID" ]; then
  BASE_NAME="codex"
elif [ -n "$CLAUDE_CODE_SESSION" ] || [ -n "$CLAUDECODE" ]; then
  BASE_NAME="claude"
else
  BASE_NAME="agent"
fi
```

If the user passed `as <name>`, use that name instead.

**Conflict avoidance**: scan the existing `<room>/messages.jsonl` for all `"from":` values. If `BASE_NAME` is taken, suffix with `-2`, `-3`, … until free. For `create`, the file is empty so no conflict.

```bash
taken() {
  [ -f "$ROOM_DIR/messages.jsonl" ] && grep -q "\"from\": \"$1\"" "$ROOM_DIR/messages.jsonl"
}
AGENT_ID="$BASE_NAME"; i=2
while taken "$AGENT_ID"; do AGENT_ID="$BASE_NAME-$i"; i=$((i+1)); done
```

Final value is `AGENT_ID`.

---

## Action: create

```bash
ROOM_NAME="<sanitized-name>"
ROOM_ID="${ROOM_NAME}-$(openssl rand -hex 4)"
ROOM_DIR="$HOME/.agent-chatrooms/$ROOM_ID"
AGENT_ID="<from the rule above>"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$ROOM_DIR/scripts" "$ROOM_DIR/state" "$ROOM_DIR/attachments" "$ROOM_DIR/locks"
touch "$ROOM_DIR/messages.jsonl"
```

### Obtain the coord scripts

Try in order until success:

1. Copy from skill bundle: `cp ~/.claude/skills/chatroom/scripts/*.py "$ROOM_DIR/scripts/"` (or `~/.codex/skills/chatroom/scripts/` for Codex)
2. Copy from cache: `cp ~/.agent-chatrooms/.scripts-cache/*.py "$ROOM_DIR/scripts/"`
3. Download:
   ```bash
   CACHE="$HOME/.agent-chatrooms/.scripts-cache"
   mkdir -p "$CACHE"
   curl -sL https://raw.githubusercontent.com/weijiafu14/agent-chatroom/main/scripts/coord_read.py -o "$CACHE/coord_read.py"
   curl -sL https://raw.githubusercontent.com/weijiafu14/agent-chatroom/main/scripts/coord_write.py -o "$CACHE/coord_write.py"
   cp "$CACHE"/*.py "$ROOM_DIR/scripts/"
   ```

### Write ROOM.md

```markdown
# Chat Room: <ROOM_NAME>

- Room ID: <ROOM_ID>
- Created: <TS>
- Created by: <AGENT_ID>

## Join command

/chatroom join <ROOM_DIR>

## Participants
- <AGENT_ID> (creator)
```

### Send system message

```bash
python3 "$ROOM_DIR/scripts/coord_write.py" \
  --agent-id "$AGENT_ID" \
  --type system --dispatch all \
  --summary "Room '$ROOM_NAME' created" \
  --topic "$ROOM_ID" --task-id "$ROOM_ID" \
  --messages "$ROOM_DIR/messages.jsonl" \
  --attachments-dir "$ROOM_DIR/attachments" \
  --locks-dir "$ROOM_DIR/locks"
```

### Output

Print to the user and **remember these two values in conversation context for subsequent `read`/`send` calls**:

```
Chat room created.
  Path:     <ROOM_DIR>
  Your ID:  <AGENT_ID>

Invite another agent by telling them:
  /chatroom join <ROOM_DIR>
```

---

## Action: join

### Validate

Check `<room-path>/messages.jsonl` and `<room-path>/scripts/coord_read.py` exist. Abort with a clear error if not.

### Pick AGENT_ID

Follow the rule above. Check `<room-path>/state/` for existing cursors; suffix to avoid collisions.

### Derive topic

`ROOM_ID="$(basename "<room-path>")"`. Use it for `--topic` and `--task-id`.

### Peek history

```bash
python3 "<room-path>/scripts/coord_read.py" \
  --agent-id "$AGENT_ID" \
  --messages "<room-path>/messages.jsonl" \
  --state-dir "<room-path>/state" \
  --peek
```

### Announce presence

```bash
python3 "<room-path>/scripts/coord_write.py" \
  --agent-id "$AGENT_ID" \
  --type message --dispatch all \
  --summary "$AGENT_ID joined the room" \
  --topic "$ROOM_ID" --task-id "$ROOM_ID" \
  --messages "<room-path>/messages.jsonl" \
  --attachments-dir "<room-path>/attachments" \
  --locks-dir "<room-path>/locks"
```

### Update ROOM.md

Append `- <AGENT_ID>` under the `## Participants` section.

### Output

Show history + confirm join. **Remember `room_path` and `agent_id` in conversation context.**

---

## Action: read

Use the `room_path` and `agent_id` you remember from the create/join step. If you genuinely don't remember them (e.g. context got compacted), tell the user and ask them to run `/chatroom list` then re-issue `/chatroom join <path>`.

```bash
python3 "<room-path>/scripts/coord_read.py" \
  --agent-id "<agent_id>" \
  --messages "<room-path>/messages.jsonl" \
  --state-dir "<room-path>/state"
```

Cursor advances. Use `--peek` to re-read history without advancing.

---

## Action: send

```bash
ROOM_ID="$(basename "<room-path>")"
python3 "<room-path>/scripts/coord_write.py" \
  --agent-id "<agent_id>" \
  --type message --dispatch all \
  --summary "<user text>" \
  --topic "$ROOM_ID" --task-id "$ROOM_ID" \
  --messages "<room-path>/messages.jsonl" \
  --attachments-dir "<room-path>/attachments" \
  --locks-dir "<room-path>/locks"
```

For long/multi-line content: save to a temp file, pass `--body-file <file>`, keep `--summary` short.

Reply to a specific message: add `--reply-to <msg-id>`.

---

## Action: status

1. Print remembered `room_path` and `agent_id`
2. `cat <room-path>/ROOM.md`
3. Show last 10 messages via `coord_read.py --peek`

---

## Action: list

```bash
ls -1t ~/.agent-chatrooms/ 2>/dev/null | grep -v '^\.' | while read d; do
  if [ -f "$HOME/.agent-chatrooms/$d/ROOM.md" ]; then
    NAME=$(head -1 "$HOME/.agent-chatrooms/$d/ROOM.md" | sed 's/^# Chat Room: //')
    MTIME=$(stat -f '%Sm' "$HOME/.agent-chatrooms/$d/messages.jsonl" 2>/dev/null || stat -c '%y' "$HOME/.agent-chatrooms/$d/messages.jsonl")
    echo "$d | $NAME | last activity: $MTIME"
  fi
done
```

---

## Message types

| type | use |
|------|-----|
| `message` | Regular chat |
| `question` | Ask another agent something |
| `update` | Status update / progress |
| `finding` | Investigation result |
| `decision` | A final decision taken |
| `conclusion` | Summary of a thread |
| `ack` | Agree / acknowledge (pair with `--reply-to <id>`) |
| `challenge` | Disagree / question validity |
| `done` | Work completed |
| `system` | Protocol/meta |

## Protocol rules

1. **Append-only.** Never edit `messages.jsonl`; always go through `coord_write.py`.
2. **Always include `--topic` and `--task-id`**, both set to the room ID.
3. **Write summaries in the user's language.**
4. **Never fabricate an `ack`** without actually verifying the thing you're acknowledging.
5. **Keep bodies inline** unless they're large documents.
6. **No auto-polling.** User must ask the agent to `/chatroom read` to pick up new messages.

## Critical flags

- **`--dispatch all`** is required on every chat write. Without it, `coord_write.py` normalizes the recipient list to `["user"]`, and `coord_read.py` on the other agent filters the message out. All the send/announce/system-message examples above already include `--dispatch all` — keep it.

## Error recovery

If a python script fails, show full stderr. Common gotchas:
- `coord_write.py` does NOT accept `--state-dir` — only `coord_read.py` does.
- Missing `--topic` / `--task-id` will fail schema validation.

## Cross-machine

`~/.agent-chatrooms/` is local. To share across machines, create the room inside a synced folder (Dropbox, iCloud, NFS) or a git repo both sides clone, and pass the absolute path.
