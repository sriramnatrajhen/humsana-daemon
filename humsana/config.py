"""
Humsana - Configuration Management
Handles ~/.humsana/config.yaml with defaults.

v2.0.0: Added webhook_type, webhook_key for PagerDuty/OpsGenie support
"""

import os
import json
import yaml
import requests
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta


# ============================================================
# PATHS
# ============================================================

def get_config_path() -> Path:
    """Get path to config file."""
    humsana_dir = Path.home() / ".humsana"
    humsana_dir.mkdir(exist_ok=True)
    return humsana_dir / "config.yaml"


def get_humsana_dir() -> Path:
    """Get the Humsana data directory."""
    humsana_dir = Path.home() / ".humsana"
    humsana_dir.mkdir(exist_ok=True)
    return humsana_dir


def get_license_path() -> Path:
    """Get path to license file."""
    return get_humsana_dir() / "license.key"


def get_license_cache_path() -> Path:
    """Get path to license cache file."""
    return get_humsana_dir() / "license_cache.json"


# License API endpoint
LICENSE_API_URL = os.getenv("HUMSANA_LICENSE_API", "https://humsana.com/license/verify")


# ============================================================
# DEFAULT PATTERNS
# ============================================================

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


# ============================================================
# LICENSE VERIFICATION
# ============================================================

@dataclass
class LicenseInfo:
    """License information."""
    valid: bool
    tier: str  # 'free', 'pro', 'team', 'enterprise'
    reason: Optional[str] = None
    expires_at: Optional[str] = None
    cached: bool = False


def verify_license() -> LicenseInfo:
    """Verify the license key."""
    license_path = get_license_path()
    cache_path = get_license_cache_path()
    
    if not license_path.exists():
        return LicenseInfo(valid=False, tier="free", reason="No license file")
    
    license_key = license_path.read_text().strip()
    
    if not license_key or not license_key.startswith("hum_pro_"):
        return LicenseInfo(valid=False, tier="free", reason="Invalid license format")
    
    # Check cache first (offline grace period: 7 days)
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
            verified_at = datetime.fromisoformat(cache["verified_at"])
            grace_period = timedelta(days=7)
            
            if datetime.utcnow() - verified_at < grace_period and cache.get("valid"):
                return LicenseInfo(
                    valid=True,
                    tier=cache.get("tier", "pro"),
                    expires_at=cache.get("expires_at"),
                    cached=True
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    
    # Verify with server
    try:
        response = requests.post(
            LICENSE_API_URL,
            json={"license_key": license_key},
            timeout=5
        )
        
        if response.ok:
            data = response.json()
            
            cache = {
                "valid": data.get("valid", False),
                "tier": data.get("tier", "pro"),
                "verified_at": datetime.utcnow().isoformat(),
                "expires_at": data.get("expires_at")
            }
            cache_path.write_text(json.dumps(cache, indent=2))
            
            return LicenseInfo(
                valid=data.get("valid", False),
                tier=data.get("tier", "pro"),
                reason=data.get("reason"),
                expires_at=data.get("expires_at")
            )
    
    except requests.RequestException:
        # Extended offline grace (30 days)
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text())
                verified_at = datetime.fromisoformat(cache["verified_at"])
                extended_grace = timedelta(days=30)
                
                if datetime.utcnow() - verified_at < extended_grace and cache.get("valid"):
                    return LicenseInfo(
                        valid=True,
                        tier=cache.get("tier", "pro"),
                        reason="Offline mode (cached)",
                        cached=True
                    )
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        
        return LicenseInfo(valid=False, tier="free", reason="Unable to verify (offline)")
    
    return LicenseInfo(valid=False, tier="free", reason="Verification failed")


# ============================================================
# CONFIG DATACLASS
# ============================================================

@dataclass
class HumsanaConfig:
    """Configuration settings for Humsana."""
    
    # === INTERLOCK SETTINGS ===
    execution_mode: str = 'dry_run'
    fatigue_threshold: int = 70
    dangerous_commands: List[str] = field(default_factory=lambda: DEFAULT_DANGEROUS_COMMANDS.copy())
    deny_patterns: List[str] = field(default_factory=list)
    allow_patterns: List[str] = field(default_factory=list)
    
    # === WEBHOOK SETTINGS (v2.0) ===
    webhook_url: Optional[str] = None
    webhook_type: str = "generic"  # "generic" | "pagerduty" | "opsgenie"
    webhook_key: Optional[str] = None  # Integration key for PD/OpsGenie
    
    # === SLACK SETTINGS (v2.0) ===
    slack_user_token: Optional[str] = None
    slack_status_expiration_minutes: int = 60  # Auto-clear after this many minutes
    
    # === ANALYSIS SETTINGS ===
    stress_threshold: float = 0.7
    focus_threshold: float = 0.6
    analysis_interval: int = 30
    batch_size: int = 100
    data_retention_days: int = 7
    webhooks: Dict[str, Any] = field(default_factory=dict)
    
    # === PRO FEATURES ===
    enable_macos_dnd: bool = False
    enable_dangerous_command_alerts: bool = True
    enable_slack_status: bool = True  # NEW: Toggle for Slack auto-status
    
    # === LICENSE (computed at runtime) ===
    _license_info: Optional[LicenseInfo] = field(default=None, repr=False)
    
    @property
    def is_pro(self) -> bool:
        """Check if user has a valid Pro license."""
        if self._license_info is None:
            self._license_info = verify_license()
        return self._license_info.valid
    
    @property
    def license_tier(self) -> str:
        """Get the current license tier."""
        if self._license_info is None:
            self._license_info = verify_license()
        return self._license_info.tier
    
    @property
    def effective_execution_mode(self) -> str:
        """Get effective execution mode based on license."""
        if self.execution_mode == "live" and not self.is_pro:
            return "dry_run"
        return self.execution_mode


# ============================================================
# CONFIG LOADING
# ============================================================

def load_config() -> HumsanaConfig:
    """Load configuration from ~/.humsana/config.yaml"""
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
            
            # Webhook settings (v2.0)
            webhook_url=data.get('webhook_url'),
            webhook_type=data.get('webhook_type', 'generic'),
            webhook_key=data.get('webhook_key'),
            
            # Slack settings (v2.0)
            slack_user_token=data.get('slack_user_token'),
            slack_status_expiration_minutes=data.get('slack_status_expiration_minutes', 60),
            enable_slack_status=data.get('enable_slack_status', True),
            
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
        
        # Webhook settings
        'webhook_type': config.webhook_type,
        
        # Slack settings
        'slack_status_expiration_minutes': config.slack_status_expiration_minutes,
        'enable_slack_status': config.enable_slack_status,
        
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
    if config.webhook_key:
        data['webhook_key'] = config.webhook_key
    if config.slack_user_token:
        data['slack_user_token'] = config.slack_user_token
    
    with open(config_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)


def get_example_config() -> str:
    """Return an example config.yaml content."""
    return """# Humsana Configuration v2.0
# Location: ~/.humsana/config.yaml

# === INTERLOCK SETTINGS ===

# Execution mode:
#   'dry_run' (default) - Simulates commands, shows what would happen
#   'live' - Actually executes commands (requires Pro license)
execution_mode: dry_run

# Fatigue threshold (0-100)
# Commands are blocked when fatigue exceeds this
fatigue_threshold: 70

# Additional dangerous patterns to block
# deny_patterns:
#   - "aws ec2 terminate"
#   - "docker rm -f"

# === NOTIFICATION SETTINGS (PRO) ===

# Slack Auto-Status
# Updates your Slack status based on your state
# Get your User Token (xoxp-...) from: https://api.slack.com/apps
# slack_user_token: xoxp-your-token-here

# Enable/disable Slack status updates
enable_slack_status: true

# Status auto-clears after this many minutes (safety net)
slack_status_expiration_minutes: 60

# === WEBHOOK SETTINGS (PRO) ===

# Webhook for safety event notifications
# webhook_url: https://events.pagerduty.com/v2/enqueue

# Webhook type: generic | pagerduty | opsgenie
# webhook_type: pagerduty

# Integration key for PagerDuty/OpsGenie
# webhook_key: your-integration-key

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
# Note: Live mode requires a Pro license ($10/month)
# Get yours at: https://humsana.com/pro

# macOS Do Not Disturb sync
enable_macos_dnd: false

# Dangerous command alerts
enable_dangerous_command_alerts: true
"""


def create_default_config() -> None:
    """Create a default config file if it doesn't exist."""
    config_path = get_config_path()
    if not config_path.exists():
        config_path.parent.mkdir(exist_ok=True)
        with open(config_path, 'w') as f:
            f.write(get_example_config())
        print(f"✅ Created default config at {config_path}")


def reset_config() -> None:
    """Reset config to defaults (overwrites existing)."""
    config_path = get_config_path()
    config_path.parent.mkdir(exist_ok=True)
    with open(config_path, 'w') as f:
        f.write(get_example_config())
    print(f"✅ Reset config to defaults at {config_path}")


def print_config() -> None:
    """Print current configuration."""
    config = load_config()
    license_info = verify_license()
    
    print("\n📋 Current Humsana Configuration:")
    print(f"   Execution mode: {config.execution_mode}")
    print(f"   Effective mode: {config.effective_execution_mode}")
    print(f"   Fatigue threshold: {config.fatigue_threshold}%")
    print(f"   Dangerous patterns: {len(config.dangerous_commands)} built-in + {len(config.deny_patterns)} custom")
    print()
    print("📡 Notifications:")
    print(f"   Slack: {'configured' if config.slack_user_token else 'not set'}")
    print(f"   Webhook: {'configured' if config.webhook_url else 'not set'}")
    if config.webhook_url:
        print(f"   Webhook type: {config.webhook_type}")
    print()
    print(f"🔐 License:")
    print(f"   Tier: {license_info.tier.upper()}")
    print(f"   Valid: {'✅ Yes' if license_info.valid else '❌ No'}")
    if license_info.reason:
        print(f"   Status: {license_info.reason}")
    if not license_info.valid:
        print(f"\n   To activate Pro: https://humsana.com/pro")
    print()


def show_license_status() -> None:
    """Display current license status."""
    info = verify_license()
    
    print("\n🔐 LICENSE STATUS")
    print("=" * 40)
    print(f"   Tier:    {info.tier.upper()}")
    print(f"   Valid:   {'✅ Yes' if info.valid else '❌ No'}")
    
    if info.reason:
        print(f"   Status:  {info.reason}")
    if info.expires_at:
        print(f"   Expires: {info.expires_at}")
    if info.cached:
        print(f"   (Using cached verification)")
    
    if not info.valid:
        print("\n   To activate Pro:")
        print("   1. Purchase at https://humsana.com/pro")
        print("   2. Save license key to ~/.humsana/license.key")
        print("   3. Restart the daemon")
    
    print()