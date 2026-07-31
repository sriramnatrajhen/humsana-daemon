"""
Humsana - Audit Logger
Logs safety overrides for compliance and post-mortems.

Writes to:
1. Local JSON file (~/.humsana/audit.json)
2. Optional webhook (for Slack/PagerDuty/etc.)
"""

import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import os


def get_audit_path() -> Path:
    """Get path to audit log file."""
    humsana_dir = Path.home() / ".humsana"
    humsana_dir.mkdir(exist_ok=True)
    return humsana_dir / "audit.json"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    event: str  # 'safety_override', 'command_blocked', 'command_allowed', 'dangerous_command_allowed'
    timestamp: str
    command: str
    fatigue_level: int
    fatigue_category: str
    uptime_hours: float
    override_reason: Optional[str]
    user: str
    outcome: str  # 'executed', 'blocked', 'simulated'
    mode: str  # 'dry_run', 'live'


class AuditLogger:
    """
    Logs safety events for compliance and analysis.
    
    Use cases:
    - Post-mortem analysis ("Why did the outage happen?")
    - Compliance reporting ("Who overrode safety in the last month?")
    - Team visibility via webhook notifications
    """
    
    # Maximum entries to keep in the log
    MAX_ENTRIES = 1000
    
    def __init__(self):
        self.audit_path = get_audit_path()
        self._load_entries()
    
    def _load_entries(self) -> None:
        """Load entries from disk."""
        if self.audit_path.exists():
            try:
                with open(self.audit_path, 'r') as f:
                    data = json.load(f)
                    self.entries = data.get('entries', [])
            except (json.JSONDecodeError, KeyError):
                self.entries = []
        else:
            self.entries = []
    
    def _save_entries(self) -> None:
        """Save entries to disk."""
        # Trim to MAX_ENTRIES (keep most recent)
        if len(self.entries) > self.MAX_ENTRIES:
            self.entries = self.entries[-self.MAX_ENTRIES:]
        
        data = {
            'entries': self.entries,
            'last_updated': datetime.now().isoformat(),
            'total_count': len(self.entries)
        }
        
        with open(self.audit_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def log_event(
        self,
        event: str,
        command: str,
        fatigue_level: int,
        fatigue_category: str,
        uptime_hours: float,
        outcome: str,
        mode: str,
        override_reason: Optional[str] = None,
        webhook_url: Optional[str] = None
    ) -> AuditEntry:
        """
        Log a safety event.
        
        Args:
            event: Type of event
            command: The command that triggered this event
            fatigue_level: User's fatigue level (0-100)
            fatigue_category: 'low', 'moderate', 'high', 'critical'
            uptime_hours: Hours since last break
            outcome: What happened ('executed', 'blocked', 'simulated')
            mode: Execution mode ('dry_run', 'live')
            override_reason: If overridden, why
            webhook_url: Optional URL to POST the event to
        
        Returns:
            The created AuditEntry
        """
        entry = AuditEntry(
            event=event,
            timestamp=datetime.now().isoformat(),
            command=command,
            fatigue_level=fatigue_level,
            fatigue_category=fatigue_category,
            uptime_hours=uptime_hours,
            override_reason=override_reason,
            user=os.environ.get('USER', 'unknown'),
            outcome=outcome,
            mode=mode
        )
        
        # Add to local log
        self.entries.append(asdict(entry))
        self._save_entries()
        
        # Fire webhook if configured
        if webhook_url:
            self._fire_webhook(entry, webhook_url)
        
        return entry
    
    def _fire_webhook(self, entry: AuditEntry, webhook_url: str) -> None:
        """
        POST the event to a webhook (Slack, PagerDuty, etc.)
        
        Fire-and-forget: doesn't block on failure.
        """
        try:
            # Format for Slack-compatible webhook
            payload = self._format_webhook_payload(entry)
            
            requests.post(
                webhook_url,
                json=payload,
                timeout=5,  # Don't hang the user's command
                headers={'Content-Type': 'application/json'}
            )
        except Exception:
            # Silently fail - webhook is best-effort
            pass
    
    def _format_webhook_payload(self, entry: AuditEntry) -> Dict[str, Any]:
        """
        Format the audit entry for Slack webhook.
        
        Returns a Slack-compatible message payload.
        """
        # Choose emoji based on event type
        emoji_map = {
            'safety_override': '🚨',
            'command_blocked': '🛑',
            'command_allowed': '✅',
            'dangerous_command_allowed': '⚠️'
        }
        emoji = emoji_map.get(entry.event, '📋')
        
        # Build the message
        text = f"{emoji} *Humsana Safety Event*\n\n"
        text += f"*Event:* {entry.event}\n"
        text += f"*User:* {entry.user}\n"
        text += f"*Command:* `{entry.command[:100]}...`\n" if len(entry.command) > 100 else f"*Command:* `{entry.command}`\n"
        text += f"*Fatigue:* {entry.fatigue_level}% ({entry.fatigue_category})\n"
        text += f"*Uptime:* {entry.uptime_hours:.1f} hours\n"
        text += f"*Outcome:* {entry.outcome}\n"
        text += f"*Mode:* {entry.mode}\n"
        
        if entry.override_reason:
            text += f"*Override Reason:* {entry.override_reason}\n"
        
        text += f"*Timestamp:* {entry.timestamp}\n"
        
        return {
            "text": text,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text
                    }
                }
            ]
        }
    
    def get_recent_events(self, count: int = 10) -> List[Dict]:
        """Get the N most recent events."""
        return self.entries[-count:]
    
    def get_overrides_since(self, since: datetime) -> List[Dict]:
        """Get all safety overrides since a given datetime."""
        return [
            e for e in self.entries
            if e['event'] == 'safety_override'
            and datetime.fromisoformat(e['timestamp']) > since
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        if not self.entries:
            return {
                'total_events': 0,
                'overrides': 0,
                'blocks': 0,
                'allowed': 0
            }
        
        return {
            'total_events': len(self.entries),
            'overrides': sum(1 for e in self.entries if e['event'] == 'safety_override'),
            'blocks': sum(1 for e in self.entries if e['event'] == 'command_blocked'),
            'allowed': sum(1 for e in self.entries if e['event'] in ('command_allowed', 'dangerous_command_allowed')),
            'oldest_entry': self.entries[0]['timestamp'] if self.entries else None,
            'newest_entry': self.entries[-1]['timestamp'] if self.entries else None
        }


# Singleton instance
_logger: Optional[AuditLogger] = None

def get_audit_logger() -> AuditLogger:
    """Get the singleton AuditLogger instance."""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger