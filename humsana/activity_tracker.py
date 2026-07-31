"""
Humsana - Activity Tracker
Tracks "Cognitive Uptime" - hours since last restorative break.

A "restorative break" is defined as 60+ minutes of inactivity.
This is the key metric for fatigue detection.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict


def get_activity_path() -> Path:
    """Get path to activity tracking file."""
    humsana_dir = Path.home() / ".humsana"
    humsana_dir.mkdir(exist_ok=True)
    return humsana_dir / "activity.json"


@dataclass
class ActivityHeartbeat:
    """A single heartbeat indicating user activity."""
    timestamp: str
    source: str  # 'keyboard', 'mouse', 'api'


class ActivityTracker:
    """
    Tracks cognitive uptime by recording activity heartbeats.
    
    Algorithm:
    1. Write a heartbeat every minute when activity is detected
    2. Look at the last 24 hours of heartbeats
    3. Find gaps > 60 minutes (these are "restorative breaks")
    4. Cognitive Uptime = time since last break
    """
    
    # A break must be at least this long to count as "restorative"
    BREAK_THRESHOLD_MINUTES = 60
    
    # How long to keep heartbeat history
    HISTORY_HOURS = 24
    
    def __init__(self):
        self.activity_path = get_activity_path()
        self._load_heartbeats()
    
    def _load_heartbeats(self) -> None:
        """Load heartbeats from disk."""
        if self.activity_path.exists():
            try:
                with open(self.activity_path, 'r') as f:
                    data = json.load(f)
                    self.heartbeats = [
                        ActivityHeartbeat(**hb) for hb in data.get('heartbeats', [])
                    ]
            except (json.JSONDecodeError, KeyError):
                self.heartbeats = []
        else:
            self.heartbeats = []
    
    def _save_heartbeats(self) -> None:
        """Save heartbeats to disk."""
        # Clean old heartbeats first
        self._cleanup_old_heartbeats()
        
        data = {
            'heartbeats': [asdict(hb) for hb in self.heartbeats],
            'last_updated': datetime.now().isoformat()
        }
        
        with open(self.activity_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _cleanup_old_heartbeats(self) -> None:
        """Remove heartbeats older than HISTORY_HOURS."""
        cutoff = datetime.now() - timedelta(hours=self.HISTORY_HOURS)
        self.heartbeats = [
            hb for hb in self.heartbeats
            if datetime.fromisoformat(hb.timestamp) > cutoff
        ]
    
    def record_activity(self, source: str = 'keyboard') -> None:
        """
        Record a heartbeat.
        Called by the daemon when activity is detected.
        """
        now = datetime.now()
        
        # Only record if we haven't recorded in the last minute
        if self.heartbeats:
            last_hb = datetime.fromisoformat(self.heartbeats[-1].timestamp)
            if (now - last_hb).total_seconds() < 60:
                return  # Too soon, skip
        
        heartbeat = ActivityHeartbeat(
            timestamp=now.isoformat(),
            source=source
        )
        self.heartbeats.append(heartbeat)
        self._save_heartbeats()
    
    def get_cognitive_uptime_hours(self) -> float:
        """
        Calculate hours of cognitive uptime since last restorative break.
        
        Returns:
            Hours since last break (>= 60 min gap)
        """
        if not self.heartbeats:
            return 0.0
        
        now = datetime.now()
        
        # Sort heartbeats by timestamp (should already be sorted, but be safe)
        sorted_hbs = sorted(
            self.heartbeats,
            key=lambda hb: datetime.fromisoformat(hb.timestamp)
        )
        
        # Find the last break (gap > BREAK_THRESHOLD_MINUTES)
        last_break_time = None
        
        for i in range(len(sorted_hbs) - 1, 0, -1):
            current = datetime.fromisoformat(sorted_hbs[i].timestamp)
            previous = datetime.fromisoformat(sorted_hbs[i-1].timestamp)
            gap_minutes = (current - previous).total_seconds() / 60
            
            if gap_minutes >= self.BREAK_THRESHOLD_MINUTES:
                last_break_time = current
                break
        
        # If no break found, use the first heartbeat as the "start"
        if last_break_time is None:
            last_break_time = datetime.fromisoformat(sorted_hbs[0].timestamp)
        
        # Calculate uptime
        uptime_hours = (now - last_break_time).total_seconds() / 3600
        return max(0.0, uptime_hours)
    
    def get_fatigue_level(self, current_stress: float = 0.0) -> int:
        """
        Calculate fatigue level (0-100) based on uptime and stress.
        
        Formula:
        - Base fatigue from uptime (0-60%)
        - Stress multiplier (adds up to 40%)
        
        Args:
            current_stress: Current stress level from daemon (0.0-1.0)
        
        Returns:
            Fatigue level 0-100
        """
        uptime = self.get_cognitive_uptime_hours()
        
        # Base fatigue from uptime
        # 0h = 0%, 4h = 20%, 8h = 40%, 12h = 60%
        base_fatigue = min(60, (uptime / 12) * 60)
        
        # Stress contribution (up to 40%)
        stress_fatigue = current_stress * 40
        
        total = int(base_fatigue + stress_fatigue)
        return min(100, max(0, total))
    
    def get_fatigue_status(self, current_stress: float = 0.0) -> Dict:
        """
        Get comprehensive fatigue status.
        
        Returns dict with:
        - fatigue_level: 0-100
        - fatigue_category: 'low', 'moderate', 'high', 'critical'
        - uptime_hours: float
        - recommendation: str
        """
        fatigue = self.get_fatigue_level(current_stress)
        uptime = self.get_cognitive_uptime_hours()
        
        if fatigue < 30:
            category = 'low'
            recommendation = 'You are fresh. Good time for complex work.'
        elif fatigue < 60:
            category = 'moderate'
            recommendation = 'You have been working a while. Consider a break in the next hour.'
        elif fatigue < 85:
            category = 'high'
            recommendation = 'High fatigue detected. Take a break before making important decisions.'
        else:
            category = 'critical'
            recommendation = 'Critical fatigue. You should stop working and rest.'
        
        return {
            'fatigue_level': fatigue,
            'fatigue_category': category,
            'uptime_hours': round(uptime, 2),
            'recommendation': recommendation,
            'break_threshold_minutes': self.BREAK_THRESHOLD_MINUTES
        }


# Singleton instance
_tracker: Optional[ActivityTracker] = None

def get_activity_tracker() -> ActivityTracker:
    """Get the singleton ActivityTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = ActivityTracker()
    return _tracker