"""
Humsana - Configuration Management
Handles ~/.humsana/config.yaml with defaults.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


def get_config_path() -> Path:
    """Get path to config file."""
    humsana_dir = Path.home() / ".humsana"
    humsana_dir.mkdir(exist_ok=True)
    return humsana_dir / "config.yaml"


# Default dangerous commands that trigger interlock
DEFAULT_DANGEROUS_COMMANDS = [
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
    "dd if=",
    "mkfs",
    "> /dev/sd",
]


@dataclass
class HumsanaConfig:
    """Configuration settings for Humsana."""
    
    # === INTERLOCK SETTINGS (Day 3) ===
    
    # Execution mode: 'dry_run' (default, simulates) or 'live' (actually executes)
    execution_mode: str = 'dry_run'
    
    # Fatigue threshold (0-100). Above this, dangerous commands are blocked.
    fatigue_threshold: int = 70
    
    # Built-in dangerous command patterns
    dangerous_commands: List[str] = field(default_factory=lambda: DEFAULT_DANGEROUS_COMMANDS.copy())
    
    # User-defined deny patterns (blocked even if fatigue is low)
    deny_patterns: List[str] = field(default_factory=list)
    
    # User-defined allow patterns (only these are allowed in live mode if set)
    allow_patterns: List[str] = field(default_factory=list)
    
    # Webhook URL for safety event notifications (Slack, PagerDuty, etc.)
    webhook_url: Optional[str] = None
    
    # === ORIGINAL SETTINGS (Day 1-2) ===
    
    # Stress threshold (0.0-1.0). Above this, user is considered "stressed"
    stress_threshold: float = 0.7
    
    # Focus threshold (0.0-1.0). Above this, user is considered "focused"
    focus_threshold: float = 0.6
    
    # How often to analyze signals (seconds)
    analysis_interval: int = 30
    
    # Batch size for signal processing
    batch_size: int = 100
    
    # How long to keep data (days)
    data_retention_days: int = 7
    
    # Webhook configurations for notifications
    webhooks: Dict[str, Any] = field(default_factory=dict)
    
    # === PRO FEATURES ===
    
    # Enable macOS Do Not Disturb sync
    enable_macos_dnd: bool = False
    
    # Enable dangerous command alerts
    enable_dangerous_command_alerts: bool = True
    
    # Slack user token for auto-status
    slack_user_token: Optional[str] = None


def load_config() -> HumsanaConfig:
    """
    Load configuration from ~/.humsana/config.yaml
    Falls back to defaults if file doesn't exist.
    """
    config_path = get_config_path()
    
    if not config_path.exists():
        return HumsanaConfig()
    
    try:
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        return HumsanaConfig(
            # Interlock settings
            execution_mode=data.get('execution_mode', 'dry_run'),
            fatigue_threshold=data.get('fatigue_threshold', 70),
            dangerous_commands=data.get('dangerous_commands', DEFAULT_DANGEROUS_COMMANDS.copy()),
            deny_patterns=data.get('deny_patterns', []),
            allow_patterns=data.get('allow_patterns', []),
            webhook_url=data.get('webhook_url'),
            
            # Original settings
            stress_threshold=data.get('stress_threshold', 0.7),
            focus_threshold=data.get('focus_threshold', 0.6),
            analysis_interval=data.get('analysis_interval', 30),
            batch_size=data.get('batch_size', 100),
            data_retention_days=data.get('data_retention_days', 7),
            webhooks=data.get('webhooks', {}),
            
            # Pro features
            enable_macos_dnd=data.get('enable_macos_dnd', False),
            enable_dangerous_command_alerts=data.get('enable_dangerous_command_alerts', True),
            slack_user_token=data.get('slack_user_token'),
        )
    except Exception as e:
        print(f"⚠️ Error loading config: {e}")
        print("Using default configuration.")
        return HumsanaConfig()


def save_config(config: HumsanaConfig) -> None:
    """Save configuration to ~/.humsana/config.yaml"""
    config_path = get_config_path()
    config_path.parent.mkdir(exist_ok=True)
    
    data = {
        # Interlock settings
        'execution_mode': config.execution_mode,
        'fatigue_threshold': config.fatigue_threshold,
        'dangerous_commands': config.dangerous_commands,
        'deny_patterns': config.deny_patterns,
        'allow_patterns': config.allow_patterns,
        
        # Original settings
        'stress_threshold': config.stress_threshold,
        'focus_threshold': config.focus_threshold,
        'analysis_interval': config.analysis_interval,
        'batch_size': config.batch_size,
        'data_retention_days': config.data_retention_days,
        'webhooks': config.webhooks,
        'enable_macos_dnd': config.enable_macos_dnd,
        'enable_dangerous_command_alerts': config.enable_dangerous_command_alerts,
    }
    
    # Only save optional fields if they exist
    if config.webhook_url:
        data['webhook_url'] = config.webhook_url
    if config.slack_user_token:
        data['slack_user_token'] = config.slack_user_token
    
    with open(config_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)


def get_example_config() -> str:
    """Return an example config.yaml content."""
    return """# Humsana Configuration
# Location: ~/.humsana/config.yaml

# === INTERLOCK SETTINGS ===

# Execution mode:
#   'dry_run' (default) - Simulates commands, shows what would happen
#   'live' - Actually executes commands
execution_mode: dry_run

# Fatigue threshold (0-100)
# Commands are blocked when fatigue exceeds this
fatigue_threshold: 70

# Additional dangerous patterns to block
# deny_patterns:
#   - "aws ec2 terminate"
#   - "docker rm -f"

# Allowlist mode (only these patterns allowed in 'live' mode)
# If empty, all commands are allowed (except dangerous ones)
# allow_patterns:
#   - "kubectl"
#   - "git"
#   - "docker"

# Webhook for safety notifications (Slack, PagerDuty, etc.)


# === ANALYSIS SETTINGS ===

# Stress threshold (0.0-1.0)
stress_threshold: 0.7

# Focus threshold (0.0-1.0)
focus_threshold: 0.6

# Analysis interval (seconds)
analysis_interval: 30

# Data retention (days)
data_retention_days: 7

# === PRO FEATURES ===

# macOS Do Not Disturb sync
enable_macos_dnd: false

# Dangerous command alerts
enable_dangerous_command_alerts: true

# Slack user token for auto-status
# slack_user_token: xoxp-your-token-here
"""