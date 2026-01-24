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

AUTH_BASE_URL = "https://humsana-auth-relay.vercel.app"
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
    """Run the Slack OAuth flow using localhost loopback."""
    
    print("🔐 Humsana Slack Authentication")
    print("=" * 50)
    print()
    
    # Check if already connected
    config = load_config()
    if config.slack_user_token:
        print("⚠️  Slack is already connected!")
        response = input("Do you want to reconnect? (y/N): ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return False
        print()
    
    # Clean up any old token file
    if _TOKEN_FILE.exists():
        _TOKEN_FILE.unlink()
    
    # Create server
    print("📡 Starting local authentication server...")
    
    try:
        socketserver.TCPServer.allow_reuse_address = True
        server = socketserver.TCPServer(("127.0.0.1", REDIRECT_PORT), OAuthCallbackHandler)
        server.timeout = 1
    except OSError as e:
        print(f"❌ Could not start server: {e}")
        return False
    
    # Run server in background
    stop_server = threading.Event()
    
    def serve():
        while not stop_server.is_set():
            server.handle_request()
    
    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()
    
    # Open browser
    auth_url = f"{AUTH_BASE_URL}/api/slack/login?port={REDIRECT_PORT}"
    
    print("🌐 Opening browser...")
    print()
    print("   If browser doesn't open, click or copy this link:")
    print()
    print(f"   \033[4m{auth_url}\033[0m")  # Underlined for visibility
    print()
    
    webbrowser.open(auth_url)
    
    print("⏳ Waiting for authorization...")
    print("   (Press Ctrl+C to cancel)")
    print()
    
    # Poll for token file
    token = None
    error = None
    start_time = time.time()
    
    try:
        while time.time() - start_time < AUTH_TIMEOUT:
            if _TOKEN_FILE.exists():
                try:
                    data = json.loads(_TOKEN_FILE.read_text())
                    token = data.get("token")
                    error = data.get("error")
                    break
                except:
                    pass
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n❌ Cancelled.")
        stop_server.set()
        server.shutdown()
        return False
    
    # Cleanup
    stop_server.set()
    try:
        server.shutdown()
    except:
        pass
    if _TOKEN_FILE.exists():
        _TOKEN_FILE.unlink()
    
    # Handle result
    if error:
        print(f"❌ Failed: {error}")
        return False
    
    if not token:
        print("❌ Timed out.")
        return False
    
    if not token.startswith("xoxp-"):
        print("❌ Invalid token format.")
        return False
    
    # Save
    config.slack_user_token = token
    save_config(config)
    
    print("=" * 50)
    print("✅ Slack connected successfully!")
    print()
    print("Run 'humsana start' to begin.")
    print("=" * 50)
    
    return True


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