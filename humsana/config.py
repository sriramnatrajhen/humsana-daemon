"""
Humsana Daemon - Configuration
Loads user configuration from ~/.humsana/config.yaml
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import yaml


def get_config_path() -> Path:
    """Get the path to the config file."""
    return Path.home() / ".humsana" / "config.yaml"


def get_default_config_path() -> Path:
    """Get the path to the default config template."""
    return Path(__file__).parent / "config.example.yaml"


@dataclass
class HumsanaConfig:
    """Configuration for the Humsana daemon."""
    
    # Dangerous commands that trigger warnings when stressed
    dangerous_commands: List[str] = field(default_factory=lambda: [
        "rm -rf",
        "DROP DATABASE",
        "DROP TABLE",
        "DELETE FROM",
        "git push --force",
        "git push -f",
        "kubectl delete",
        "terraform destroy",
        "docker system prune",
        "sudo rm",
        "format c:",
        "mkfs",
    ])
    
    # Stress threshold (0.0 to 1.0) for triggering warnings
    stress_threshold: float = 0.7
    
    # Focus threshold for detecting deep work
    focus_threshold: float = 0.6
    
    # Analysis interval (seconds between analyses)
    analysis_interval: float = 5.0
    
    # Batch size (keystrokes before analysis)
    batch_size: int = 20
    
    # Data retention (days to keep local data)
    data_retention_days: int = 7
    
    # Webhooks for DIY integrations (Linux users, etc.)
    webhooks: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "on_focus_start": None,
        "on_focus_end": None,
        "on_high_stress": None,
        "on_state_change": None,
    })
    
    # Focus Shield Pro settings (requires subscription)
    slack_user_token: Optional[str] = None
    enable_macos_dnd: bool = False
    enable_dangerous_command_alerts: bool = True


def load_config() -> HumsanaConfig:
    """
    Load configuration from ~/.humsana/config.yaml
    Falls back to defaults if file doesn't exist.
    """
    config_path = get_config_path()
    
    if not config_path.exists():
        # Create default config
        create_default_config()
        return HumsanaConfig()
    
    try:
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        return HumsanaConfig(
            dangerous_commands=data.get('dangerous_commands', [
                "rm -rf",
                "DROP DATABASE",
                "DROP TABLE",
                "DELETE FROM",
                "git push --force",
                "git push -f",
                "kubectl delete",
                "terraform destroy",
                "docker system prune",
                "sudo rm",
            ]),
            stress_threshold=data.get('stress_threshold', 0.7),
            focus_threshold=data.get('focus_threshold', 0.6),
            analysis_interval=data.get('analysis_interval', 5.0),
            batch_size=data.get('batch_size', 20),
            data_retention_days=data.get('data_retention_days', 7),
            webhooks=data.get('webhooks', {}),
            slack_user_token=data.get('slack_user_token'),
            enable_macos_dnd=data.get('enable_macos_dnd', False),
            enable_dangerous_command_alerts=data.get('enable_dangerous_command_alerts', True),
        )
    
    except Exception as e:
        print(f"⚠️ Error loading config: {e}")
        print("Using default configuration.")
        return HumsanaConfig()


def create_default_config() -> None:
    """Create the default config file."""
    config_dir = Path.home() / ".humsana"
    config_dir.mkdir(exist_ok=True)
    
    config_path = config_dir / "config.yaml"
    
    default_config = """# Humsana Configuration
# Edit this file to customize behavior

# Commands that trigger warnings when you're stressed
dangerous_commands:
  - "rm -rf"
  - "DROP DATABASE"
  - "DROP TABLE"
  - "DELETE FROM"
  - "git push --force"
  - "git push -f"
  - "kubectl delete"
  - "terraform destroy"
  - "docker system prune"
  - "sudo rm"

# Thresholds (0.0 to 1.0)
stress_threshold: 0.7
focus_threshold: 0.6

# Analysis settings
analysis_interval: 5.0  # seconds between analyses
batch_size: 20          # keystrokes before analysis

# Data retention
data_retention_days: 7

# Webhooks for DIY integrations
# Set these to HTTP URLs to get notified of events
webhooks:
  on_focus_start: null
  on_focus_end: null
  on_high_stress: null
  on_state_change: null

# ===========================================
# FOCUS SHIELD PRO SETTINGS (requires $10/mo subscription)
# ===========================================

# Slack integration (get token from: https://api.slack.com/legacy/oauth)
# slack_user_token: xoxp-your-token-here

# macOS Do Not Disturb sync
enable_macos_dnd: false

# Dangerous command alerts in Claude
enable_dangerous_command_alerts: true
"""
    
    with open(config_path, 'w') as f:
        f.write(default_config)
    
    print(f"✅ Created default config at: {config_path}")


def save_config(config: HumsanaConfig) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(exist_ok=True)
    
    data = {
        'dangerous_commands': config.dangerous_commands,
        'stress_threshold': config.stress_threshold,
        'focus_threshold': config.focus_threshold,
        'analysis_interval': config.analysis_interval,
        'batch_size': config.batch_size,
        'data_retention_days': config.data_retention_days,
        'webhooks': config.webhooks,
        'enable_macos_dnd': config.enable_macos_dnd,
        'enable_dangerous_command_alerts': config.enable_dangerous_command_alerts,
    }
    
    # Only save slack token if it exists
    if config.slack_user_token:
        data['slack_user_token'] = config.slack_user_token
    
    with open(config_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)