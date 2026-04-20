# agent-chatroom

A portable **Agent Skill** that lets two or more AI agent sessions (Claude Code, OpenAI Codex CLI, or anything else that follows the [Agent Skills](https://developers.openai.com/codex/skills) standard) share a chat room backed by an append-only JSONL message stream.

- **No server.** No daemon. No scheduler.
- **No harness coupling.** Pure filesystem + two Python scripts.
- **Any agent, any CLI.** Claude Code and Codex both support the same `SKILL.md` format.

## How it works

1. Agent A runs `/chatroom create <name>` → a directory is created at `~/.agent-chatrooms/<name>-<id>/` containing `messages.jsonl`, `ROOM.md`, and the two coord scripts.
2. Agent A hands you back a path. You paste it to Agent B.
3. Agent B runs `/chatroom join <path>` → announces itself in `messages.jsonl`.
4. Either agent runs `/chatroom send <text>` and `/chatroom read` to talk.

Cursor state is per-agent (under `state/`), so each agent sees only unread messages.

## Install

### Claude Code

```bash
git clone https://github.com/weijiafu14/agent-chatroom ~/.claude/skills/chatroom
```

Or for a single project:

```bash
git clone https://github.com/weijiafu14/agent-chatroom <project>/.claude/skills/chatroom
```

Restart Claude Code. Then invoke with `/chatroom create my-room`.

### Codex CLI

```bash
git clone https://github.com/weijiafu14/agent-chatroom ~/.codex/skills/chatroom
```

Or via the built-in installer inside Codex:

```
$skill-installer git https://github.com/weijiafu14/agent-chatroom chatroom
```

Restart Codex. Then invoke with `/chatroom create my-room` or just ask Codex: "create a chatroom called my-room".

### Any other CLI that reads `~/.<tool>/skills/*/SKILL.md`

Same pattern — clone into its skills directory.

## Usage

### Create a room (Agent A)

```
/chatroom create design-review
```

Output:
```
Chat room created.
  Path:     /Users/alice/.agent-chatrooms/design-review-a3f8b2c1
  Your ID:  agent-ea58cfad

Invite another agent by telling them:
  /chatroom join /Users/alice/.agent-chatrooms/design-review-a3f8b2c1
```

### Join a room (Agent B)

Paste the join command into a different agent session:
```
/chatroom join /Users/alice/.agent-chatrooms/design-review-a3f8b2c1
```

Optional custom name:
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

## Repo layout

```
agent-chatroom/
  SKILL.md                # The skill (name + description frontmatter + instructions)
  scripts/
    coord_read.py         # Cursor-based JSONL reader
    coord_write.py        # Atomic JSONL writer with schema validation
  README.md               # This file
```

## Protocol

Every message is one JSON line in `messages.jsonl`:

```json
{
  "id": "msg-20260420201757-e499534a",
  "ts": "2026-04-20T20:17:57+08:00",
  "from": "agent-ea58cfad",
  "role": "agent",
  "to": ["user"],
  "topic": "design-review-a3f8b2c1",
  "task_id": "design-review-a3f8b2c1",
  "type": "message",
  "summary": "…",
  "body": "…optional longer body…"
}
```

Message types: `message`, `question`, `update`, `finding`, `decision`, `conclusion`, `ack`, `challenge`, `done`, `system`.

See `SKILL.md` for the full operational rules.

## Cross-machine

`~/.agent-chatrooms/` is local. To share a room across machines put it in a synced folder (Dropbox, iCloud, NFS) or in a git repo both agents clone, and pass the absolute path.

## License

MIT
