# Humsana Daemon

🔒 **100% Local. Auditable Code. No Data Exfiltration.**

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Humsana monitors your typing patterns to detect stress and focus levels. Your AI assistant (Claude) can use this to adapt responses — brief when you're stressed, detailed when you're relaxed.

## 🎯 What It Does

```
You typing fast, lots of backspaces, erratic rhythm
→ Humsana detects: STRESSED (0.8)
→ Claude: Gives you a brief, direct answer

You typing steadily, consistent flow, no corrections
→ Humsana detects: FOCUSED (0.9)
→ Claude: Doesn't interrupt with clarifying questions
```

## 🔒 Privacy Guarantee

**We never capture what you type.**

| What We Capture | What We DON'T Capture |
|-----------------|----------------------|
| ✅ Time between keystrokes | ❌ Key codes |
| ✅ Backspace count (not content) | ❌ Characters typed |
| ✅ Typing rhythm variance | ❌ Passwords |
| ✅ Session duration | ❌ Screen content |

All data stays in `~/.humsana/signals.db` on your machine.

**Audit the code yourself:** See `humsana/collector.py` lines 65-95 for the exact privacy implementation.

## 🔐 Why Accessibility Permissions?

macOS requires Accessibility permission for any app that monitors keyboard input — even if we only measure *timing* and never capture actual keys.

**This feels scary. Here's why it's safe:**

1. **We're open source.** Every line of code is auditable. We can't hide anything.

2. **We never see your keystrokes.** Look at `humsana/collector.py` lines 65-95:
   ```python
   # We check the key to categorize, then discard it
   is_backspace = (key == keyboard.Key.backspace)
   
   # Create privacy-safe signal
   # NOTE: 'key' is NOT stored in SignalSnapshot
   signal = SignalSnapshot(
       timestamp=now,
       interval_ms=interval_ms,  # Only timing!
       is_backspace=is_backspace,
       is_modifier=is_modifier
   )
   ```

3. **Data never leaves your machine.** Check `humsana/local_db.py` — it's pure SQLite at `~/.humsana/signals.db`. No network calls in the free tier.

4. **You can verify network activity:**
   ```bash
   # Watch for any network connections (there should be none)
   sudo lsof -i -n -P | grep humsana
   ```

**If you're still uncomfortable:** Run the daemon in a VM or container, or audit every line before installing. We built this because we'd want to use it ourselves.

## 📦 Installation

```bash
pip install humsana-daemon
```

### macOS Accessibility Setup

After installing, macOS will require Accessibility permissions:

1. Run `humsana start`
2. You'll see: "This process is not trusted!"
3. Go to **System Preferences → Security & Privacy → Privacy → Accessibility**
4. Click the 🔒 lock and add your Terminal app
5. **Restart Terminal completely** (Cmd+Q, not just close window)
6. Run `humsana start` again

## 🚀 Quick Start

```bash
# Start the daemon
humsana start

# Check your current state (in another terminal)
humsana status

# View/edit config
humsana config
```

## 🤖 Claude Desktop Integration

1. Install the MCP server:
```bash
npm install -g @humsana/mcp-server
```

2. Add to `~/.config/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "humsana": {
      "command": "npx",
      "args": ["@humsana/mcp-server"]
    }
  }
}
```

3. Restart Claude Desktop

Now Claude will automatically adapt to your mental state!

## ⚙️ Configuration

Edit `~/.humsana/config.yaml`:

```yaml
# Commands that trigger warnings when you're stressed
dangerous_commands:
  - "rm -rf"
  - "DROP DATABASE"
  - "git push --force"
  - "kubectl delete"
  - "terraform destroy"

# Thresholds (0.0 to 1.0)
stress_threshold: 0.7
focus_threshold: 0.6

# Webhooks for DIY integrations
webhooks:
  on_focus_start: null
  on_focus_end: null
  on_high_stress: null
```

## 📊 States Detected

| State | What It Means | AI Response Style |
|-------|---------------|-------------------|
| 🟢 RELAXED | Low activity, calm | Friendly, detailed |
| 🔵 WORKING | Normal activity | Detailed, helpful |
| 🔷 FOCUSED | Deep work, flow state | Don't interrupt |
| 🟡 STRESSED | High velocity, corrections | Brief, direct |
| 🔴 DEBUGGING | High stress + high activity | Concise, solutions only |

## 🛡️ Focus Shield Pro ($10/mo)

Upgrade for additional features:

- **Slack Auto-Status**: Auto-set "🔴 Deep Focus" when you're in flow
- **macOS DND Sync**: Automatically enable Do Not Disturb
- **Dangerous Command Alerts**: Claude warns you before destructive commands

[Get Focus Shield →](https://humsana.com/pro)

## 🔧 For Linux Users

The daemon works on Linux! For DND/Slack sync, use the webhooks:

```yaml
webhooks:
  on_focus_start: "http://localhost:8080/focus-start"
  on_focus_end: "http://localhost:8080/focus-end"
```

Then write your own script to handle these events.

## 🐛 Troubleshooting

### "Permission denied" or "not trusted" on macOS

macOS requires Accessibility permissions for keyboard monitoring:

1. Go to **System Preferences → Security & Privacy → Privacy → Accessibility**
2. Click the 🔒 lock to make changes
3. Click **+** and add your terminal app:
   - `/Applications/Utilities/Terminal.app` (default Terminal)
   - `/Applications/iTerm.app` (if using iTerm2)
   - `/Applications/Visual Studio Code.app` (if running from VS Code terminal)
4. **Restart your terminal completely** (Cmd+Q)
5. Run `humsana start` again

### Daemon not detecting keystrokes

```bash
# Check if daemon is running
humsana status

# If no recent data, restart
humsana start
```

### High CPU usage

The daemon should use <1% CPU. If higher:

```bash
# Check analysis interval in config
humsana config
# Increase analysis_interval to 10.0 or higher
```

### Verify no network activity

```bash
# This should return nothing (no connections)
sudo lsof -i -n -P | grep -i humsana
```

## 📜 License

MIT License — do whatever you want with it.

## 🤝 Contributing

PRs welcome! Especially for:
- Linux DND integrations
- Windows support improvements
- Additional state detection algorithms

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/sriramnatrajhen/humsana-daemon/issues)
- **Email**: hello@humsana.com

---

**Built with frustration after almost dropping a production database at 2am.**