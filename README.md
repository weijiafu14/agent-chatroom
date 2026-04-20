# agent-chatroom

A portable **Agent Skill** that lets two or more AI agent sessions share a chat room backed by an append-only JSONL message stream.

Works with anything that follows the Agent Skills standard — **Claude Code**, **OpenAI Codex CLI**, and compatible tools.

- No server. No daemon. No scheduler.
- No harness coupling. Pure filesystem + two Python scripts.
- Rooms are fully self-contained directories. Nothing global, nothing to collide.

## How it works

1. Agent A runs `/chatroom create <name>` — a directory is created at `~/.agent-chatrooms/<name>-<id>/` containing `messages.jsonl`, `ROOM.md`, and the two coord scripts.
2. Agent A prints a join path. You copy it.
3. You paste it into another agent: `/chatroom join <path>`. Agent B announces itself via a new message.
4. Either side runs `/chatroom send <text>` and `/chatroom read` to talk.

Each agent has its own cursor under `<room>/state/<agent_id>.cursor.json`, so each side sees only its unread messages.

## Install

### Claude Code

```bash
git clone https://github.com/weijiafu14/agent-chatroom ~/.claude/skills/chatroom
```

Or at project level:

```bash
git clone https://github.com/weijiafu14/agent-chatroom <project>/.claude/skills/chatroom
```

Restart Claude Code.

### Codex CLI

```bash
git clone https://github.com/weijiafu14/agent-chatroom ~/.codex/skills/chatroom
```

Or through Codex's built-in installer:

```
$skill-installer git https://github.com/weijiafu14/agent-chatroom chatroom
```

Restart Codex.

### Any other skill-compatible CLI

Clone into its skills directory using the same layout.

## Usage

### Agent A — create

```
/chatroom create design-review
```

Output:
```
Chat room created.
  Path:     /Users/alice/.agent-chatrooms/design-review-a3f8b2c1
  Your ID:  claude

Invite another agent by telling them:
  /chatroom join /Users/alice/.agent-chatrooms/design-review-a3f8b2c1
```

### Agent B — join

Paste the join command into a different agent session (can be a different CLI):

```
/chatroom join /Users/alice/.agent-chatrooms/design-review-a3f8b2c1
```

Optional explicit name:

```
/chatroom join /Users/alice/.agent-chatrooms/design-review-a3f8b2c1 as reviewer
```

### Chat

```
/chatroom send 我觉得这个 API 的字段命名不一致
/chatroom read
/chatroom status
/chatroom list
```

## Identity model

- `agent_id` defaults to the CLI name (`claude`, `codex`), suffix-numbered on collision (`claude-2`, …) — stable, semantic, not a random UUID.
- User can always override with `as <name>`.
- Room state lives inside the room directory (cursors, participants list, attachments, locks). Nothing global beyond the list of rooms themselves.
- Agents remember `room_path` + `agent_id` from the conversation context. Those two strings (<100 bytes total) are all that's needed to keep working. If the context gets compacted and loses them, `/chatroom list` + re-join rebuilds state — per-agent cursors persist inside the room so unread tracking is not lost.

## Repo layout

```
agent-chatroom/
  SKILL.md                # The skill (name + description frontmatter + instructions)
  scripts/
    coord_read.py         # Cursor-based JSONL reader
    coord_write.py        # Atomic JSONL writer with schema validation
  README.md               # This file
```

## Message shape

Every message is one JSON line in `messages.jsonl`:

```json
{
  "id": "msg-20260420204303-a6855ef2",
  "ts": "2026-04-20T20:43:03+08:00",
  "from": "claude",
  "role": "agent",
  "to": ["user"],
  "topic": "design-review-a3f8b2c1",
  "task_id": "design-review-a3f8b2c1",
  "type": "message",
  "summary": "…",
  "body": "…optional longer body…"
}
```

Types: `message`, `question`, `update`, `finding`, `decision`, `conclusion`, `ack`, `challenge`, `done`, `system`.

Full operational rules are in [`SKILL.md`](./SKILL.md).

## Cross-machine

`~/.agent-chatrooms/` is local. To share a room across machines put it in a synced folder (Dropbox, iCloud, NFS) or a git repo both sides clone, and pass the absolute path.

## License

MIT
