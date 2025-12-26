"""
Humsana Daemon
🔒 100% Local. Auditable Code. No Data Exfiltration.

AI that reads the room - stress and focus detection for Claude.
"""

__version__ = "1.0.0"
__author__ = "Humsana"
__license__ = "MIT"

from .collector import SignalCollector, SignalSnapshot
from .analyzer import SignalAnalyzer, AnalysisResult, UserState
from .local_db import LocalDatabase, get_db_path
from .config import HumsanaConfig, load_config, get_config_path
from .activity_tracker import get_activity_tracker, ActivityTracker
from .audit import get_audit_logger, AuditLogger
from .interlock import get_interlock, HumsanaInterlock, InterlockResult

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
]