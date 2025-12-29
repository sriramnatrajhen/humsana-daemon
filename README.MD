# humsana-daemon

Local behavioral signal collection for Humsana Cognitive Security.

> 🛡️ "The breathalyzer for your terminal."

## What It Does

Humsana daemon runs locally on your machine, collecting behavioral signals (typing patterns, activity) to detect fatigue. It works with the Humsana MCP server to prevent dangerous commands when you're tired.

## Installation
```bash
pip install humsana-daemon
```

## Usage
```bash
# Start the daemon
humsana start

# Check status
humsana status

# Stop
humsana stop
```

## Privacy

🔒 **100% Local.** All data stays on your machine in `~/.humsana/`. No network calls, no telemetry.

## Works With

- [Humsana MCP Server](https://github.com/sriramnatrajhen/humsana-mcp) — Claude Desktop integration

## License

MIT
