"""
Humsana Daemon v2.0
🔒 100% Local. Auditable Code. No Data Exfiltration.

AI that reads the room - stress and focus detection for Claude.

v2.0 Features:
- ADRENALINE state detection (P0/Flow mode - don't block)
- FATIGUED state detection (sloppy - should block)
- Slack auto-status updates
- PagerDuty/OpsGenie webhook support
"""

__version__ = "2.0.0"
__author__ = "Humsana"
__license__ = "MIT"

from .collector import SignalCollector, SignalSnapshot
from .analyzer import SignalAnalyzer, AnalysisResult, UserState
from .local_db import LocalDatabase, get_db_path
from .config import HumsanaConfig, load_config, get_config_path
from .activity_tracker import get_activity_tracker, ActivityTracker
from .audit import get_audit_logger, AuditLogger
from .interlock import get_interlock, HumsanaInterlock, InterlockResult
from .notifications import NotificationManager  # NEW
from .auth import authenticate_slack, disconnect_slack, show_auth_status

__all__ = [
    # Collector
    "SignalCollector",
    "SignalSnapshot",
    
    # Analyzer
    "SignalAnalyzer",
    "AnalysisResult",
    "UserState",
    
    # Database
    "LocalDatabase",
    "get_db_path",
    
    # Config
    "HumsanaConfig",
    "load_config",
    "get_config_path",
    
    # Activity Tracker
    "get_activity_tracker",
    "ActivityTracker",
    
    # Audit
    "get_audit_logger",
    "AuditLogger",
    
    # Interlock
    "get_interlock",
    "HumsanaInterlock",
    "InterlockResult",
    
    # Notifications (NEW)
    "NotificationManager",

    # Slack
    'authenticate_slack',
    'disconnect_slack', 
    'show_auth_status',
]