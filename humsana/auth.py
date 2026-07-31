"""
Humsana Auth - Localhost Loopback OAuth Flow
Uses a temp file for cross-thread signaling (most reliable method).
"""

import webbrowser
import http.server
import socketserver
import urllib.parse
import threading
import tempfile
import time
import os
import json
from pathlib import Path
from typing import Optional

from .config import load_config, save_config, get_config_path

# ============================================================
# CONFIGURATION
# ============================================================

# One-click OAuth relay retired; Slack is configured manually now.
REDIRECT_PORT = 3649
AUTH_TIMEOUT = 120

# Temp file for passing token from handler to main thread
_TOKEN_FILE = Path(tempfile.gettempdir()) / "humsana_oauth_result.json"


# ============================================================
# HTTP HANDLER
# ============================================================

class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handle the OAuth callback from the relay server."""
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if 'token' in params:
            token = params['token'][0]
            # Write token to temp file (main thread will read it)
            _TOKEN_FILE.write_text(json.dumps({"token": token}))
            self._send_success_page()
                
        elif 'error' in params:
            error = params.get('error', ['Unknown error'])[0]
            _TOKEN_FILE.write_text(json.dumps({"error": error}))
            self._send_error_page(error)
        else:
            self.send_error(400, "Invalid callback")
    
    def _send_success_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = b"""<!DOCTYPE html>
<html><head><title>Humsana</title>
<style>body{font-family:-apple-system,sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#1a1a2e;color:white;text-align:center;}</style></head>
<body><div><div style="font-size:64px;">&#x2705;</div><h1>Slack Connected!</h1><p style="color:#888;">You can close this window.</p></div>
<script>setTimeout(function(){window.close();},2000);</script></body></html>"""
        self.wfile.write(html)
    
    def _send_error_page(self, error: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = f"""<!DOCTYPE html>
<html><head><title>Humsana</title>
<style>body{{font-family:-apple-system,sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#1a1a2e;color:white;text-align:center;}}</style></head>
<body><div><div style="font-size:64px;">&#x274C;</div><h1 style="color:#ff6b6b;">Failed</h1><p style="color:#888;">{error}</p></div></body></html>""".encode()
        self.wfile.write(html)
    
    def log_message(self, format, *args):
        pass


# ============================================================
# MAIN AUTH FUNCTION
# ============================================================

def authenticate_slack() -> bool:
    """One-click Slack connect has been retired (the hosted relay was shut down).

    Slack status updates still work if you provide your own token: create a Slack
    app with the users.profile:write scope and set slack_user_token in
    ~/.humsana/config.yaml. Humsana never sees your token."""
    print("\nℹ️  One-click Slack setup has been retired.")
    print("   Slack status still works with your own token:")
    print("   1. Create a Slack app: https://api.slack.com/apps  (scope: users.profile:write)")
    print("   2. Add to ~/.humsana/config.yaml:")
    print("        slack_user_token: xoxp-your-token-here")
    print("        enable_slack_status: true")
    return False


def disconnect_slack() -> bool:
    """Remove Slack token from config."""
    config = load_config()
    
    if not config.slack_user_token:
        print("ℹ️  Slack is not connected.")
        return False
    
    config.slack_user_token = None
    save_config(config)
    
    print("✅ Slack disconnected.")
    return True


def show_auth_status():
    """Show current authentication status."""
    config = load_config()
    
    print("🔐 Humsana Authentication Status")
    print("=" * 50)
    print()
    
    if config.slack_user_token:
        token = config.slack_user_token
        masked = f"{token[:8]}...{token[-4:]}"
        print(f"✅ Slack: Connected")
        print(f"   Token: {masked}")
    else:
        print("❌ Slack: Not connected")
        print("   Run 'humsana auth' to connect")
    
    print()
    print(f"📁 Config: {get_config_path()}")