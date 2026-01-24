"""
Humsana Daemon - Command Line Interface v2
Main entry point for the daemon.

v2.0: Integrated NotificationManager for Slack + Webhooks

Usage:
    humsana start     # Start the daemon
    humsana stop      # Stop the daemon
    humsana status    # Show current state
    humsana config    # Open config file
    humsana test-slack    # Test Slack connection (NEW)
    humsana test-webhook  # Test webhook (NEW)
"""

import argparse
import sys
import signal
import time
import json
from pathlib import Path
from typing import Optional

from .collector import SignalCollector
from .analyzer import SignalAnalyzer, AnalysisResult
from .local_db import LocalDatabase, get_db_path
from .config import load_config, get_config_path, create_default_config
from .notifications import NotificationManager  # NEW
from .auth import authenticate_slack, disconnect_slack, show_auth_status


# Global daemon instance for signal handling
_daemon: Optional['HumsanaDaemon'] = None


class HumsanaDaemon:
    """
    Main daemon that coordinates collection, analysis, storage, and notifications.
    
    v2.0: Added NotificationManager for Slack auto-status and webhooks
    """
    
    def __init__(self):
        self.config = load_config()
        self.db = LocalDatabase()
        self.analyzer = SignalAnalyzer()
        self.collector = SignalCollector(on_signal_batch=self._on_signals)
        
        # NEW: Initialize notification manager
        self.notifier = NotificationManager(
            slack_user_token=self.config.slack_user_token if self.config.enable_slack_status else None,
            webhook_url=self.config.webhook_url,
            webhook_type=self.config.webhook_type,
            webhook_key=self.config.webhook_key,
        )
        
        self.session_id: Optional[int] = None
        self._running = False
        self._last_state: Optional[str] = None
    
    def _on_signals(self, signals: list) -> None:
        """Called when collector has a batch of signals."""
        # Get idle time
        idle_seconds = self.collector.get_idle_seconds()
        
        # Analyze signals
        result = self.analyzer.analyze(signals, idle_seconds)
        
        # Store in database
        self.db.store_analysis(result)
        
        # NEW: Update notifications (Slack status)
        self.notifier.update_state(
            result.state.value,
            {
                "stress_level": result.stress_level,
                "focus_level": result.focus_level,
                "typing_wpm": result.typing_wpm,
            }
        )
        
        # Check for state change (for legacy webhooks)
        if self._last_state != result.state.value:
            self._on_state_change(self._last_state, result.state.value)
            self._last_state = result.state.value
        
        # Print status (if verbose)
        self._print_status(result)
    
    def _on_state_change(self, old_state: Optional[str], new_state: str) -> None:
        """Handle state transitions."""
        # Call legacy webhook if configured
        webhook_url = self.config.webhooks.get('on_state_change')
        if webhook_url:
            self._call_webhook(webhook_url, {
                'event': 'state_change',
                'old_state': old_state,
                'new_state': new_state
            })
        
        # Special handling for focus transitions
        if new_state == 'focused':
            focus_url = self.config.webhooks.get('on_focus_start')
            if focus_url:
                self._call_webhook(focus_url, {'event': 'focus_start'})
        
        elif old_state == 'focused':
            focus_url = self.config.webhooks.get('on_focus_end')
            if focus_url:
                self._call_webhook(focus_url, {'event': 'focus_end'})
        
        # High stress alert
        if new_state in ('stressed', 'debugging', 'fatigued'):
            stress_url = self.config.webhooks.get('on_high_stress')
            if stress_url:
                self._call_webhook(stress_url, {'event': 'high_stress', 'state': new_state})
    
    def _call_webhook(self, url: str, data: dict) -> None:
        """Call a webhook URL with data."""
        try:
            import requests
            requests.post(url, json=data, timeout=5)
        except Exception as e:
            print(f"⚠️ Webhook failed: {e}")
    
    def _print_status(self, result: AnalysisResult) -> None:
        """Print current status."""
        # Color coding for terminal
        state_colors = {
            'relaxed': '\033[92m',    # Green
            'working': '\033[94m',    # Blue
            'focused': '\033[96m',    # Cyan
            'stressed': '\033[93m',   # Yellow
            'debugging': '\033[91m',  # Red
            'fatigued': '\033[95m',   # Magenta (NEW)
            'adrenaline': '\033[97m', # White/Bold (NEW)
        }
        reset = '\033[0m'
        
        color = state_colors.get(result.state.value, '')
        
        print(f"\r{color}[{result.state.value.upper():^10}]{reset} "
              f"Stress: {result.stress_level:.2f} | "
              f"Focus: {result.focus_level:.2f} | "
              f"WPM: {result.typing_wpm:.0f} | "
              f"Confidence: {result.confidence:.2f}",
              end='', flush=True)
    
    def start(self) -> None:
        """Start the daemon."""
        print("🚀 Starting Humsana daemon v2.0...")
        print(f"📁 Database: {get_db_path()}")
        print(f"⚙️ Config: {get_config_path()}")
        print("")
        print("🔒 Privacy mode: ONLY timing data collected")
        print("📖 Audit the code: https://github.com/sriramnatrajhen/humsana-daemon")
        print("")
        
        # Show notification status
        if self.config.slack_user_token and self.config.enable_slack_status:
            print("📡 Slack auto-status: ENABLED")
        if self.config.webhook_url:
            print(f"🔔 Webhook ({self.config.webhook_type}): ENABLED")
        
        print("")
        print("Press Ctrl+C to stop")
        print("-" * 60)
        
        self._running = True
        self.session_id = self.db.start_session()
        self.collector.start()
        
        # Keep running until stopped
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the daemon."""
        if not self._running:
            return
        
        self._running = False
        self.collector.stop()
        
        # NEW: Clear Slack status on clean shutdown
        if self.notifier:
            self.notifier.clear_slack_status()
        
        if self.session_id:
            self.db.end_session(self.session_id)
        
        # Cleanup old data
        deleted = self.db.cleanup_old_data(self.config.data_retention_days)
        if deleted > 0:
            print(f"\n🧹 Cleaned up {deleted} old records")
        
        print("\n👋 Humsana daemon stopped")
    
    def get_status(self) -> dict:
        """Get current status for CLI or MCP."""
        metrics = self.db.get_average_metrics(minutes=5)
        state = self.db.get_dominant_state(minutes=5)
        current = self.db.get_current_state()
        
        return {
            'state': state,
            'metrics': metrics,
            'current': current,
            'session_id': self.session_id,
            'running': self._running
        }


def cmd_start(args):
    """Start the daemon."""
    global _daemon
    
    # Set up signal handlers
    def handle_signal(signum, frame):
        if _daemon:
            _daemon.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    _daemon = HumsanaDaemon()
    _daemon.start()

def cmd_auth(args):
    """Handle auth command."""
    if args.action == 'status':
        show_auth_status()
    elif args.action == 'disconnect':
        disconnect_slack()
    else:
        # Default: connect Slack
        authenticate_slack()


def cmd_status(args):
    """Show current status."""
    db = LocalDatabase()
    metrics = db.get_average_metrics(minutes=5)
    state = db.get_dominant_state(minutes=5)
    current = db.get_current_state()
    
    print("📊 Humsana Status")
    print("-" * 40)
    
    if metrics['sample_count'] == 0:
        print("⚠️ No recent data. Is the daemon running?")
        print(f"\nStart with: humsana start")
        return
    
    # State with color
    state_colors = {
        'relaxed': '\033[92m',
        'working': '\033[94m',
        'focused': '\033[96m',
        'stressed': '\033[93m',
        'debugging': '\033[91m',
        'fatigued': '\033[95m',
        'adrenaline': '\033[97m',
    }
    reset = '\033[0m'
    color = state_colors.get(state, '')
    
    print(f"State: {color}{state.upper()}{reset}")
    print(f"Stress: {metrics['stress_level']:.2f}")
    print(f"Focus: {metrics['focus_level']:.2f}")
    print(f"Cognitive Load: {metrics['cognitive_load']:.2f}")
    print(f"Typing WPM: {metrics['typing_wpm']:.0f}")
    print(f"Samples (5 min): {metrics['sample_count']}")
    
    if current:
        print(f"\nRecommendation: {current.get('response_style', 'N/A')}")
        print(f"Interruptible: {'Yes' if current.get('interruptible') else 'No'}")


def cmd_config(args):
    """Open or create config file."""
    config_path = get_config_path()
    
    if not config_path.exists():
        create_default_config()
    
    print(f"📁 Config file: {config_path}")
    print("\nTo edit, run:")
    print(f"  nano {config_path}")
    print(f"  # or")
    print(f"  code {config_path}")


def cmd_export(args):
    """Export current state as JSON (for MCP)."""
    db = LocalDatabase()
    metrics = db.get_average_metrics(minutes=5)
    state = db.get_dominant_state(minutes=5)
    current = db.get_current_state()
    
    output = {
        'state': state,
        'stress_level': metrics['stress_level'],
        'focus_level': metrics['focus_level'],
        'cognitive_load': metrics['cognitive_load'],
        'recommendations': {
            'response_style': current.get('response_style', 'friendly') if current else 'friendly',
            'avoid_clarifying_questions': bool(current.get('avoid_clarifying_questions', False)) if current else False,
            'interruptible': bool(current.get('interruptible', True)) if current else True,
        },
        'sample_count': metrics['sample_count'],
        'window_minutes': metrics['window_minutes']
    }
    
    print(json.dumps(output, indent=2))


# NEW: Test Slack connection
def cmd_test_slack(args):
    """Test Slack connection."""
    config = load_config()
    
    if not config.slack_user_token:
        print("❌ No Slack token configured")
        print("\nTo configure:")
        print("1. Create a Slack app at https://api.slack.com/apps")
        print("2. Add 'users.profile:write' scope")
        print("3. Install to workspace and copy User OAuth Token")
        print("4. Add to ~/.humsana/config.yaml:")
        print("   slack_user_token: xoxp-your-token-here")
        return
    
    notifier = NotificationManager(slack_user_token=config.slack_user_token)
    result = notifier.test_slack_connection()
    
    if result.get("ok"):
        print(f"✅ Slack connected!")
        print(f"   User: {result.get('user')}")
        print(f"   Team: {result.get('team')}")
        
        # Test setting status
        print("\n🧪 Testing status update...")
        notifier._update_slack_status("focused")
        print("   Set status to '🧠 Deep Focus'")
        
        time.sleep(2)
        
        notifier.clear_slack_status()
        print("   Cleared status")
        print("\n✅ Slack integration working!")
    else:
        print(f"❌ Slack connection failed: {result.get('error')}")


# NEW: Test webhook
def cmd_test_webhook(args):
    """Test webhook connection."""
    config = load_config()
    
    if not config.webhook_url:
        print("❌ No webhook URL configured")
        print("\nTo configure, add to ~/.humsana/config.yaml:")
        print("   webhook_url: https://your-webhook-url")
        print("   webhook_type: generic  # or 'pagerduty' or 'opsgenie'")
        print("   webhook_key: your-integration-key  # for PD/OpsGenie")
        return
    
    notifier = NotificationManager(
        webhook_url=config.webhook_url,
        webhook_type=config.webhook_type,
        webhook_key=config.webhook_key,
    )
    
    print(f"🧪 Testing webhook ({config.webhook_type})...")
    print(f"   URL: {config.webhook_url[:50]}...")
    
    success = notifier.test_webhook()
    
    if success:
        print("✅ Webhook test sent successfully!")
    else:
        print("❌ Webhook test failed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Humsana v2.0 - AI that reads the room',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  humsana start           Start the daemon
  humsana status          Show current state
  humsana auth            Connect Slack (opens browser, zero friction!)
  humsana auth status     Show what's connected
  humsana auth disconnect Remove Slack connection
  humsana config          Open config file
  humsana export          Export state as JSON (for MCP)
  humsana test-slack      Test Slack connection

Privacy:
  🔒 Humsana only collects timing between keystrokes
  🔒 We NEVER capture what you type
  🔒 All data stays local in ~/.humsana/
  
More info: https://github.com/sriramnatrajhen/humsana-daemon
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # start command
    start_parser = subparsers.add_parser('start', help='Start the daemon')
    start_parser.set_defaults(func=cmd_start)
    
    # status command
    status_parser = subparsers.add_parser('status', help='Show current status')
    status_parser.set_defaults(func=cmd_status)
    
    # config command
    config_parser = subparsers.add_parser('config', help='Open config file')
    config_parser.set_defaults(func=cmd_config)
    
    # export command (for MCP)
    export_parser = subparsers.add_parser('export', help='Export state as JSON')
    export_parser.set_defaults(func=cmd_export)
    
    # NEW: test-slack command
    test_slack_parser = subparsers.add_parser('test-slack', help='Test Slack connection')
    test_slack_parser.set_defaults(func=cmd_test_slack)
    
    # NEW: test-webhook command
    test_webhook_parser = subparsers.add_parser('test-webhook', help='Test webhook')
    test_webhook_parser.set_defaults(func=cmd_test_webhook)

    auth_parser = subparsers.add_parser('auth', help='Connect Slack (zero friction)')
    auth_parser.add_argument('action', nargs='?', default='connect',
                             choices=['connect', 'status', 'disconnect'],
                             help='Auth action (default: connect)')
    auth_parser.set_defaults(func=cmd_auth)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == '__main__':
    main()