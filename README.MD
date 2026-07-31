# Humsana Daemon

Local behavioral signal collection for Humsana Cognitive Security.

> 🛡️ "The breathalyzer for your terminal."

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## What It Does

Humsana daemon runs locally on your machine, detecting fatigue from your typing patterns. When you're tired and try to run a dangerous command (`rm -rf`, `DROP TABLE`, `kubectl delete`), it blocks you.

**Features:**
- 🧠 **Cognitive Interlock** — Blocks dangerous commands when fatigued
- 🔒 **100% Local** — All data stays on your machine, no accounts, no network calls
- 🔌 **Works with Claude** — Exposes your state to AI tools via the Humsana MCP server

## Installation
```bash
pip install humsana-daemon
```

## Quick Start
```bash
# Start the daemon
humsana start

# Check your current state
humsana status
```

## Commands

| Command | Description |
|---------|-------------|
| `humsana start` | Start the daemon |
| `humsana status` | Show current stress/focus/fatigue levels |
| `humsana config` | Open config file |
| `humsana export` | Export state as JSON (for MCP) |

## How It Works
```
You're tired at 2am, debugging for 8 hours straight.
→ You type: rm -rf ./
→ Humsana detects: fatigue 78%, cognitive load high
→ 🛑 INTERLOCK ENGAGED: Command blocked
→ You can override: "OVERRIDE SAFETY PROTOCOL: P0 production outage"
→ Everything logged to audit trail
```

## Privacy & Security

### What Humsana Collects

| Data | Collected? | Details |
|------|------------|---------|
| Keystrokes (what you type) | ❌ NO | Never captured |
| Timing between keystrokes | ✅ Yes | Used to detect typing rhythm |
| Mouse movements | ❌ NO | Not tracked |
| Screen content | ❌ NO | Never captured |
| Application names | ❌ NO | Not tracked |

### Where Data Lives

- **All behavioral data stays on your machine** in `~/.humsana/signals.db`
- **No data is ever sent to any server** — the daemon makes no network calls by default
- No accounts, no telemetry, no tracking

### Data Deletion

To remove all Humsana data:
```bash
rm -rf ~/.humsana
```

## Configuration

Config lives at `~/.humsana/config.yaml`:
```yaml
# Fatigue threshold (0-100) - commands blocked above this
fatigue_threshold: 70

# Commands that trigger the interlock when fatigued
dangerous_commands:
  - "rm -rf"
  - "DROP DATABASE"
  - "DROP TABLE"
  - "git push --force"
  - "kubectl delete"
  - "terraform destroy"
```

## Works With

- [Humsana MCP Server](https://github.com/sriramnatrajhen/humsana-mcp) — Claude Desktop integration

## Auditing the Code

This project is 100% open source and 100% local:

- [Daemon code](https://github.com/sriramnatrajhen/humsana-daemon) — What runs on your machine
- [Humsana MCP Server](https://github.com/sriramnatrajhen/humsana-mcp) — The Claude Desktop bridge

## License

MIT
