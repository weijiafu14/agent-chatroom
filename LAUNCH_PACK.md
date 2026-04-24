# agent-chatroom launch pack

## Positioning

**One-line pitch**

A zero-infra chat room skill for multi-agent coordination. Claude Code, Codex, and other skill-compatible CLIs can talk through a shared append-only JSONL room.

**Chinese one-line pitch**

一个零基础设施的多 Agent 协作技能：让 Claude Code、Codex 等 agent 直接在同一个 JSONL 聊天室里对话协作。

## Core hooks

### Hook 1 — anti-overengineering

Most multi-agent projects start with orchestration.
This one starts with a chat room.

### Hook 2 — zero infra

No server. No daemon. No scheduler.
Just a room directory, a `messages.jsonl`, and two small Python scripts.

### Hook 3 — cross-agent

Claude Code and Codex can coordinate through the same room.

## Who this is for

- people experimenting with multi-agent workflows
- users comparing Claude Code vs Codex vs other agent CLIs
- builders who want a portable coordination primitive before building a heavier stack
- anyone who prefers filesystem-native tools over hosted orchestration systems

## Differentiators

- append-only protocol instead of hidden state
- self-contained room directory
- per-agent unread cursors
- explicit message types
- explicit lock / decision / reply semantics
- works as a skill, not a standalone service

## English X post

Built a new skill: **agent-chatroom**

It gives Claude Code, Codex, and other skill-compatible agent CLIs a shared chat room backed by an append-only JSONL stream.

- no server
- no daemon
- no scheduler
- no orchestration stack required

Just create a room, join from another agent, then `/chatroom send` + `/chatroom read`.

Repo: https://github.com/weijiafu14/agent-chatroom

## English X post — punchier

Multi-agent coordination is often overengineered.

So I built **agent-chatroom**:
a zero-infra skill that lets Claude Code, Codex, and other agent CLIs talk through a shared append-only JSONL room.

Portable. Inspectable. No backend.

https://github.com/weijiafu14/agent-chatroom

## 中文社群文案

我刚发了一个新 skill：**agent-chatroom**。

它不是那种重型 multi-agent orchestration 框架，而是一个更底层、也更好用的协作原语：
让 Claude Code、Codex 这类 agent，直接通过一个 append-only 的 `messages.jsonl` 聊天室互相发消息、同步进度、做协作。

特点：
- 不需要 server
- 不需要 daemon
- 不需要 scheduler
- 房间就是一个目录，状态全在本地，可检查、可同步、可归档

适合拿来做：
- 多 agent 代码评审
- 并行 research 协作
- planner / executor 分工
- Claude Code 和 Codex 的 cross-agent 实验

仓库：
https://github.com/weijiafu14/agent-chatroom

## GitHub release / README intro short form

**agent-chatroom** is a zero-infra coordination skill for AI agents.
It lets Claude Code, Codex, and other compatible CLIs exchange structured messages through a shared append-only JSONL room.

## Hacker News / Reddit angle

Instead of building a full orchestrator for multi-agent experiments, I built the smallest coordination primitive I actually wanted:

- a room is just a directory
- messages live in `messages.jsonl`
- each agent keeps its own cursor
- no server required
- works across agent CLIs

The idea is to make multi-agent coordination portable, inspectable, and easy to hack on.

Repo: https://github.com/weijiafu14/agent-chatroom

## Suggested posting order

1. Push README + LICENSE first
2. Post a short X thread or one-liner
3. Share to Claude Code / Codex / OpenClaw / AI agent communities
4. Follow with a 20–30s demo gif if available

## Best next assets

- a terminal gif showing create → join → send → read
- a diagram showing one room directory shared by two agents
- one concrete example: Claude reviews, Codex challenges, both converge via decision/ack
