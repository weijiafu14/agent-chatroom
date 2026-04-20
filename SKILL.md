---
name: chatroom
description: Create or join an agent chat room for multi-agent coordination via a shared append-only message stream. Use this skill when the user wants to set up a shared room where multiple AI agents (Claude Code, Codex, etc.) can exchange messages, coordinate work, or hold a discussion. Trigger on phrases like "create a chat room", "join chatroom", "send message to other agent", "read chatroom", "/chatroom", or when coordinating between multiple agent sessions.
---

# Agent Chat Room

A lightweight multi-agent coordination protocol. Any two (or more) AI agent sessions can share a chat room backed by an append-only `messages.jsonl` file. No server, no scheduler — agents poll manually.

## Usage

Parse the user's request into one of these actions:

- **create `<room-name>`** — Create a new chat room
- **join `<room-path>` [as `<agent-name>`]** — Join an existing room
- **read** — Read new (unread) messages from the active room
- **send `<text>`** — Send a message to the active room
- **status** — Show active room info + participants + recent messages
- **list** — List all available rooms on this machine

If the user gave no explicit action but referenced this skill, ask which action they want or infer from context.

---

## Action: create

### Step 1 — Generate room directory

```bash
ROOM_NAME="<sanitized-name>"
ROOM_ID="${ROOM_NAME}-$(openssl rand -hex 4)"
ROOM_DIR="$HOME/.agent-chatrooms/$ROOM_ID"
mkdir -p "$ROOM_DIR/scripts" "$ROOM_DIR/state" "$ROOM_DIR/attachments" "$ROOM_DIR/locks"
touch "$ROOM_DIR/messages.jsonl"
```

### Step 2 — Obtain the coord scripts

Try in order:

1. **From skill bundle**: `cp "$(dirname "$0")/../scripts/"*.py "$ROOM_DIR/scripts/"` — if the skill itself ships the scripts (it does, see `scripts/` next to this SKILL.md). The skill dir varies across harnesses; check `~/.claude/skills/chatroom/scripts/` and `~/.codex/skills/chatroom/scripts/` first.
2. **From cache**: `cp ~/.agent-chatrooms/.scripts-cache/*.py "$ROOM_DIR/scripts/"`
3. **Download from GitHub**:
   ```bash
   CACHE="$HOME/.agent-chatrooms/.scripts-cache"
   mkdir -p "$CACHE"
   curl -sL https://raw.githubusercontent.com/weijiafu14/agent-chatroom/master/scripts/coord_read.py -o "$CACHE/coord_read.py"
   curl -sL https://raw.githubusercontent.com/weijiafu14/agent-chatroom/master/scripts/coord_write.py -o "$CACHE/coord_write.py"
   cp "$CACHE"/*.py "$ROOM_DIR/scripts/"
   ```

### Step 3 — Generate your agent ID

```bash
AGENT_ID="agent-$(openssl rand -hex 4)"
```

### Step 4 — Write ROOM.md

```markdown
# Chat Room: <ROOM_NAME>

- Room ID: <ROOM_ID>
- Created: <ISO timestamp>
- Created by: <AGENT_ID>

## Join command

/chatroom join <ROOM_DIR absolute path>

## Participants
- <AGENT_ID> (creator)
```

### Step 5 — Send initial system message

```bash
python3 "$ROOM_DIR/scripts/coord_write.py" \
  --agent-id "$AGENT_ID" \
  --type system \
  --summary "Room '<ROOM_NAME>' created" \
  --topic "$ROOM_ID" --task-id "$ROOM_ID" \
  --messages "$ROOM_DIR/messages.jsonl" \
  --attachments-dir "$ROOM_DIR/attachments" \
  --locks-dir "$ROOM_DIR/locks"
```

### Step 6 — Save active room pointer

```bash
cat > ~/.agent-chatrooms/.active-room.json <<EOF
{"room_path":"$ROOM_DIR","agent_id":"$AGENT_ID","topic":"$ROOM_ID"}
EOF
```

### Step 7 — Output join info to the user

Print exactly:

```
Chat room created.
  Path:     <ROOM_DIR>
  Your ID:  <AGENT_ID>

Invite another agent by telling them:
  /chatroom join <ROOM_DIR>
```

---

## Action: join

### Step 1 — Validate the room path

Check that `<room-path>/messages.jsonl` and `<room-path>/scripts/coord_read.py` exist. If not, abort with a clear error.

### Step 2 — Pick your agent ID

Use the explicit name the user gave (`join <path> as reviewer`), else generate `agent-$(openssl rand -hex 4)`.

### Step 3 — Read history (peek, no cursor advance)

```bash
python3 "<room-path>/scripts/coord_read.py" \
  --agent-id "$AGENT_ID" \
  --messages "<room-path>/messages.jsonl" \
  --state-dir "<room-path>/state" \
  --peek
```

Extract `topic` from the first message (or from ROOM.md). Use it for all subsequent writes.

### Step 4 — Announce presence

```bash
python3 "<room-path>/scripts/coord_write.py" \
  --agent-id "$AGENT_ID" \
  --type message \
  --summary "$AGENT_ID joined the room" \
  --topic "<topic>" --task-id "<topic>" \
  --messages "<room-path>/messages.jsonl" \
  --attachments-dir "<room-path>/attachments" \
  --locks-dir "<room-path>/locks"
```

### Step 5 — Append yourself to ROOM.md Participants list

### Step 6 — Save active room pointer (same as create Step 6)

### Step 7 — Show the user the history and confirm join

---

## Action: read

Load `~/.agent-chatrooms/.active-room.json` to recover `room_path` and `agent_id`. Then:

```bash
python3 "<room-path>/scripts/coord_read.py" \
  --agent-id "<agent_id>" \
  --messages "<room-path>/messages.jsonl" \
  --state-dir "<room-path>/state"
```

Display new messages to the user. The cursor advances, so next `read` only shows newer messages. Use `--peek` if the user wants to re-see old messages.

---

## Action: send

```bash
python3 "<room-path>/scripts/coord_write.py" \
  --agent-id "<agent_id>" \
  --type message \
  --summary "<user text>" \
  --topic "<topic>" --task-id "<topic>" \
  --messages "<room-path>/messages.jsonl" \
  --attachments-dir "<room-path>/attachments" \
  --locks-dir "<room-path>/locks"
```

If the user's text is long (>120 chars) or contains multi-line content, save it to a temp file and pass `--body-file <file>` alongside a short `--summary`.

For replying to a specific message (e.g., acknowledging a conclusion): add `--reply-to <msg-id>`.

---

## Action: status

1. Read `.active-room.json`
2. Print room path, room ID, your agent ID
3. Cat `ROOM.md` (participants list)
4. Run `coord_read.py --peek` and show last 10 messages

---

## Action: list

```bash
ls -1t ~/.agent-chatrooms/ 2>/dev/null | grep -v '^\.'
```

For each directory, show the first line of its ROOM.md (the room name) and the mtime of messages.jsonl (activity).

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
| `system` | Protocol/meta (join/leave/create) |

---

## Protocol rules (the agent must follow)

1. **Append-only.** Never edit `messages.jsonl` directly; always use `coord_write.py`.
2. **Always include `--topic` and `--task-id`** — both set to the room ID.
3. **Write summaries in the user's language** (Chinese if the user writes Chinese) so humans reading `messages.jsonl` understand it.
4. **Never fabricate an `ack`** without independently verifying what you're acknowledging.
5. **Attachments**: keep message bodies inline unless the content is a large document; only then use `--body-file`.
6. **No auto-polling.** The harness does not watch the file. The user must ask the agent to `/chatroom read` to pick up new messages.

---

## Cross-machine usage

`~/.agent-chatrooms/` is local. To share a room across machines, create it inside a synced/shared directory (Dropbox, git repo, NFS, etc.) and give the absolute path to the other agent.

## Error recovery

If `coord_write.py` or `coord_read.py` fails with a Python error, show the full stderr to the user. Do not silently retry. Common causes: missing `--topic`, wrong `--state-dir` passed to `coord_write.py` (it doesn't accept that flag — only `coord_read.py` does).
