"""
Humsana Notifications - v1.0
Handles external communications: Slack status updates and Webhooks.

This is a PRO feature that provides:
1. Slack Auto-Status: Updates your status to "🧠 Deep Focus" automatically
2. Webhook Alerts: POSTs to PagerDuty/OpsGenie when safety events occur

Privacy: Only sends state labels, never behavioral data.
"""

import time
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SlackStatus:
    """Slack status configuration."""
    text: str
    emoji: str


class NotificationManager:
    """
    Manages external notifications for Humsana.
    
    Features:
    - Slack auto-status with expiration (prevents "zombie statuses")
    - PagerDuty/OpsGenie formatted webhooks
    - Generic webhook support
    """
    
    # Slack status mapping
    STATUS_MAP: Dict[str, SlackStatus] = {
        "focused": SlackStatus(text="Deep Focus", emoji=":brain:"),
        "adrenaline": SlackStatus(text="Handling Incident", emoji=":rotating_light:"),
        "fatigued": SlackStatus(text="Low Battery", emoji=":battery:"),
        "stressed": SlackStatus(text="Busy", emoji=":warning:"),
        "debugging": SlackStatus(text="Debugging", emoji=":bug:"),
        "working": SlackStatus(text="Working", emoji=":computer:"),
        "relaxed": SlackStatus(text="", emoji=""),  # Clear status
    }
    
    # Status expiration (safety net for crashed daemons)
    STATUS_EXPIRATION_SECONDS = 3600  # 1 hour
    
    def __init__(
        self,
        slack_user_token: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_type: str = "generic",  # "generic" | "pagerduty" | "opsgenie"
        webhook_key: Optional[str] = None,
    ):
        """
        Initialize the notification manager.
        
        Args:
            slack_user_token: Slack user token (xoxp-...) for status updates
            webhook_url: URL to POST safety events to
            webhook_type: Type of webhook ("generic", "pagerduty", "opsgenie")
            webhook_key: Integration key for PagerDuty/OpsGenie
        """
        self.slack_user_token = slack_user_token
        self.webhook_url = webhook_url
        self.webhook_type = webhook_type
        self.webhook_key = webhook_key
        
        # Track last status to avoid API spam
        self.last_slack_status: Optional[SlackStatus] = None
        self.last_state: Optional[str] = None
    
    def update_state(self, state: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Called whenever the analyzer determines a new state.
        Updates Slack status if configured.
        
        Args:
            state: The new user state (e.g., "focused", "fatigued")
            metrics: Optional metrics dict (not sent externally)
        """
        # Only update if state changed
        if state == self.last_state:
            return
        
        self.last_state = state
        
        # Update Slack status if token exists
        if self.slack_user_token:
            self._update_slack_status(state)
    
    def send_safety_alert(
        self, 
        event_type: str, 
        details: Dict[str, Any]
    ) -> bool:
        """
        Called when Interlock blocks or overrides a command.
        Sends to configured webhook.
        
        Args:
            event_type: "blocked" | "override" | "allowed"
            details: Event details (command, fatigue, etc.)
        
        Returns:
            True if webhook was sent successfully
        """
        if not self.webhook_url:
            return False
        
        try:
            payload = self._format_webhook_payload(event_type, details)
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5,
                headers={"Content-Type": "application/json"}
            )
            
            return response.ok
            
        except Exception as e:
            # Fail silently - webhooks are best-effort
            print(f"⚠️ Webhook failed: {e}")
            return False
    
    def _update_slack_status(self, state: str) -> bool:
        """
        Sets Slack status emoji and text.
        
        Includes expiration as a safety net - if the daemon crashes,
        the status will auto-clear after 1 hour.
        
        Args:
            state: The user state
        
        Returns:
            True if status was updated successfully
        """
        # Handle idle/relaxed - clear status immediately
        if state in ("relaxed", "idle"):
            return self._set_slack_status("", "", 0)
        
        # Get status for this state
        status = self.STATUS_MAP.get(state)
        if not status:
            return False
        
        # Don't API spam if status hasn't changed
        if status == self.last_slack_status:
            return True
        
        # Set expiration for safety net
        # If daemon dies, status clears automatically in 1 hour
        expiration = int(time.time()) + self.STATUS_EXPIRATION_SECONDS
        
        success = self._set_slack_status(status.text, status.emoji, expiration)
        
        if success:
            self.last_slack_status = status
        
        return success
    
    def _set_slack_status(
        self, 
        text: str, 
        emoji: str, 
        expiration: int
    ) -> bool:
        """
        Make the actual Slack API call.
        
        Args:
            text: Status text (e.g., "Deep Focus")
            emoji: Status emoji (e.g., ":brain:")
            expiration: Unix timestamp when status should auto-clear
        
        Returns:
            True if API call succeeded
        """
        if not self.slack_user_token:
            return False
        
        try:
            url = "https://slack.com/api/users.profile.set"
            headers = {
                "Authorization": f"Bearer {self.slack_user_token}",
                "Content-Type": "application/json"
            }
            data = {
                "profile": {
                    "status_text": text,
                    "status_emoji": emoji,
                    "status_expiration": expiration
                }
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=5)
            result = response.json()
            
            return result.get("ok", False)
            
        except Exception as e:
            print(f"⚠️ Slack status update failed: {e}")
            return False
    
    def _format_webhook_payload(
        self, 
        event_type: str, 
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format webhook payload based on webhook_type.
        
        Supports:
        - PagerDuty Events API v2
        - OpsGenie (similar format)
        - Generic JSON
        """
        
        # PAGERDUTY FORMAT
        if self.webhook_type == "pagerduty":
            severity = "error" if event_type == "blocked" else "warning"
            
            return {
                "routing_key": self.webhook_key,
                "event_action": "trigger",
                "dedup_key": f"humsana-{event_type}-{int(time.time())}",
                "payload": {
                    "summary": f"Humsana Safety Interlock: {event_type.upper()}",
                    "source": "humsana-daemon",
                    "severity": severity,
                    "custom_details": {
                        "event": event_type,
                        "command": details.get("command", "unknown")[:100],
                        "fatigue_level": details.get("fatigue_level", 0),
                        "fatigue_category": details.get("fatigue_category", "unknown"),
                        "uptime_hours": details.get("uptime_hours", 0),
                        "override_reason": details.get("override_reason"),
                        "user": details.get("user", "unknown"),
                    }
                }
            }
        
        # OPSGENIE FORMAT
        elif self.webhook_type == "opsgenie":
            priority = "P1" if event_type == "blocked" else "P3"
            
            return {
                "message": f"Humsana: {event_type.upper()} - {details.get('command', 'unknown')[:50]}",
                "alias": f"humsana-{event_type}-{int(time.time())}",
                "priority": priority,
                "source": "humsana-daemon",
                "details": {
                    "event": event_type,
                    "command": details.get("command", "unknown"),
                    "fatigue_level": str(details.get("fatigue_level", 0)),
                    "fatigue_category": details.get("fatigue_category", "unknown"),
                    "uptime_hours": str(details.get("uptime_hours", 0)),
                }
            }
        
        # GENERIC FORMAT (Slack-compatible)
        else:
            emoji_map = {
                "blocked": "🛑",
                "override": "🚨",
                "allowed": "✅",
            }
            emoji = emoji_map.get(event_type, "📋")
            
            return {
                "event": event_type,
                "level": "warning" if event_type == "blocked" else "info",
                "message": f"{emoji} Humsana Safety Event: {event_type}",
                "details": details,
                "timestamp": int(time.time())
            }
    
    def clear_slack_status(self) -> bool:
        """
        Explicitly clear Slack status.
        Call this when daemon shuts down cleanly.
        """
        self.last_slack_status = None
        return self._set_slack_status("", "", 0)
    
    def test_slack_connection(self) -> Dict[str, Any]:
        """
        Test if Slack token is valid.
        Returns connection status.
        """
        if not self.slack_user_token:
            return {"ok": False, "error": "No Slack token configured"}
        
        try:
            url = "https://slack.com/api/auth.test"
            headers = {"Authorization": f"Bearer {self.slack_user_token}"}
            response = requests.get(url, headers=headers, timeout=5)
            return response.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def test_webhook(self) -> bool:
        """
        Send a test webhook.
        Returns True if successful.
        """
        return self.send_safety_alert(
            event_type="test",
            details={
                "message": "Humsana webhook test",
                "fatigue_level": 0,
                "fatigue_category": "low",
                "command": "echo 'test'",
            }
        )