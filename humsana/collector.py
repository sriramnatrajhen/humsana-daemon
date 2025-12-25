"""
Humsana Daemon - Signal Collector
🔒 100% Local. Auditable Code. No Data Exfiltration.

This module captures typing patterns to detect stress and focus levels.
CRITICAL PRIVACY GUARANTEE:
- We NEVER store what you type (no key codes, no characters)
- We ONLY store timing between keystrokes
- All data stays in local SQLite (~/.humsana/signals.db)

See lines 45-70 for the exact privacy implementation.
"""

from pynput import keyboard, mouse
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable
import time
import threading


@dataclass
class SignalSnapshot:
    """
    A privacy-safe snapshot of typing behavior.
    Contains ONLY timing data, never key content.
    """
    timestamp: float
    interval_ms: float  # Time since last keystroke
    is_backspace: bool  # Only track if it was a correction
    is_modifier: bool   # Shift, Ctrl, Alt, Cmd


class SignalCollector:
    """
    Collects behavioral signals from keyboard and mouse.
    
    PRIVACY IMPLEMENTATION (lines 45-70):
    - on_key_press() receives the key but IMMEDIATELY discards it
    - We only extract: timestamp, interval, is_backspace, is_modifier
    - The actual key character is NEVER stored or transmitted
    """
    
    def __init__(self, on_signal_batch: Optional[Callable] = None):
        # Rolling buffer of recent signals (last 1000)
        self.signals: deque[SignalSnapshot] = deque(maxlen=1000)
        
        # Timing tracking
        self.last_key_time: Optional[float] = None
        self.session_start: float = time.time()
        
        # Callback when we have enough signals to analyze
        self.on_signal_batch = on_signal_batch
        self.batch_size = 20  # Analyze every 20 keystrokes
        self.batch_count = 0
        
        # Listeners (will be started by start())
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None
        self._running = False
    
    # =========================================================
    # PRIVACY-CRITICAL SECTION: Lines 65-95
    # This is where we handle raw keyboard input.
    # Auditors: verify that we NEVER store key.char or key.vk
    # =========================================================
    
    def _on_key_press(self, key) -> None:
        """
        Handle a key press event.
        
        PRIVACY GUARANTEE:
        - We extract ONLY timing and type information
        - The actual key value is checked but NEVER stored
        - After this function, the key object is garbage collected
        """
        now = time.time()
        
        # Calculate interval since last keystroke
        interval_ms = 0.0
        if self.last_key_time is not None:
            interval_ms = (now - self.last_key_time) * 1000
        
        # Detect key TYPE only (not content)
        # We check the key to categorize, then discard it
        is_backspace = (key == keyboard.Key.backspace)
        is_modifier = key in (
            keyboard.Key.shift, keyboard.Key.shift_r,
            keyboard.Key.ctrl, keyboard.Key.ctrl_r,
            keyboard.Key.alt, keyboard.Key.alt_r,
            keyboard.Key.cmd, keyboard.Key.cmd_r
        )
        
        # Create privacy-safe signal
        # NOTE: 'key' is NOT stored in SignalSnapshot
        signal = SignalSnapshot(
            timestamp=now,
            interval_ms=interval_ms,
            is_backspace=is_backspace,
            is_modifier=is_modifier
        )
        
        # Store the signal (key object goes out of scope here)
        self.signals.append(signal)
        self.last_key_time = now
        
        # Trigger batch analysis
        self.batch_count += 1
        if self.batch_count >= self.batch_size and self.on_signal_batch:
            self.batch_count = 0
            # Pass a copy of recent signals for analysis
            self.on_signal_batch(list(self.signals))
    
    # =========================================================
    # END PRIVACY-CRITICAL SECTION
    # =========================================================
    
    def _on_key_release(self, key) -> None:
        """Handle key release - currently unused but available for future."""
        pass
    
    def _on_mouse_click(self, x: int, y: int, button, pressed: bool) -> None:
        """
        Handle mouse clicks.
        We track click timing for activity detection, not coordinates.
        """
        if pressed:
            # Just update activity timestamp
            self.last_key_time = time.time()
    
    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        """Track scroll activity for focus detection."""
        self.last_key_time = time.time()
    
    def start(self) -> None:
        """Start collecting signals."""
        if self._running:
            return
        
        self._running = True
        
        # Start keyboard listener
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self._keyboard_listener.start()
        
        # Start mouse listener
        self._mouse_listener = mouse.Listener(
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll
        )
        self._mouse_listener.start()
        
        print("🎯 Humsana collector started")
        print("🔒 Privacy mode: ONLY timing data collected")
    
    def stop(self) -> None:
        """Stop collecting signals."""
        self._running = False
        
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        
        print("⏹️ Humsana collector stopped")
    
    def get_recent_signals(self, count: int = 100) -> list[SignalSnapshot]:
        """Get the most recent signals for analysis."""
        signals_list = list(self.signals)
        return signals_list[-count:] if len(signals_list) > count else signals_list
    
    def get_session_duration_seconds(self) -> float:
        """How long has this session been running?"""
        return time.time() - self.session_start
    
    def get_idle_seconds(self) -> float:
        """How long since last activity?"""
        if self.last_key_time is None:
            return 0.0
        return time.time() - self.last_key_time