# Humsana Daemon

Local behavioral signal collection for Humsana Cognitive Security.

> 🛡️ "The breathalyzer for your terminal."

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## What It Does

Humsana daemon runs locally on your machine, detecting fatigue from your typing patterns. When you're tired and try to run a dangerous command (`rm -rf`, `DROP TABLE`, `kubectl delete`), it blocks you.

**Features:**
- 🧠 **Cognitive Interlock** — Blocks dangerous commands when fatigued
- 📡 **Slack Auto-Status** — Team sees when you're in deep focus (optional)
- 🔒 **100% Local** — All data stays on your machine
- ⚡ **Zero Friction Auth** — Connect Slack with one click

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

# Connect Slack for auto-status (optional)
humsana auth
```

## Commands

| Command | Description |
|---------|-------------|
| `humsana start` | Start the daemon |
| `humsana status` | Show current stress/focus/fatigue levels |
| `humsana auth` | Connect Slack (opens browser, zero friction) |
| `humsana auth status` | Show what's connected |
| `humsana auth disconnect` | Remove Slack connection |
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

## Slack Integration

Connect Slack to automatically update your status based on your state:
```bash
humsana auth
```

A browser opens → click "Allow" → done. Your teammates will see:

| Your State | Slack Status |
|------------|--------------|
| Deep focus | 🧠 Deep Focus |
| Stressed | ⚠️ Busy |
| Handling incident | 🚨 Handling Incident |
| Fatigued | 🔋 Low Battery |

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
- **No data is ever sent to Humsana servers**
- Your Slack token is stored locally in `~/.humsana/config.yaml`

### Slack OAuth Flow

When you run `humsana auth`:

1. Your browser opens Slack's authorization page
2. You click "Allow" to grant status-update permission
3. Slack sends a token through our relay server
4. The token is **immediately redirected** to your local machine
5. **We never store your Slack token** — it passes through RAM only

The relay server is open source: [humsana-auth-relay](https://github.com/sriramnatrajhen/humsana-auth-relay)

### Slack Permissions Requested

| Permission | Why |
|------------|-----|
| `users.profile:write` | Update your Slack status |
| `users.profile:read` | Verify connection works |

### Data Deletion

To remove all Humsana data:
```bash
rm -rf ~/.humsana
```

To revoke Slack access: Slack Settings → Apps → Humsana Status → Remove

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

# Slack auto-status
enable_slack_status: true
```

## Works With

- [Humsana MCP Server](https://github.com/sriramnatrajhen/humsana-mcp) — Claude Desktop integration

## Auditing the Code

This project is 100% open source:

- [Daemon code](https://github.com/sriramnatrajhen/humsana-daemon) — What runs on your machine
- [Auth relay](https://github.com/sriramnatrajhen/humsana-auth-relay) — Stateless OAuth handler

## License

MIT