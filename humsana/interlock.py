"""
Humsana Interlock - Cognitive Safety Engine
The "Breathalyzer for the Terminal"

Prevents execution of dangerous commands when user is fatigued.
Implements the "Break Glass" protocol for overrides.
"""

import re
import subprocess
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

from .config import load_config, HumsanaConfig
from .activity_tracker import get_activity_tracker
from .audit import get_audit_logger
from .local_db import LocalDatabase


@dataclass
class InterlockResult:
    """Result of an interlock check."""
    allowed: bool
    status: str  # 'allowed', 'blocked', 'override_required', 'simulated'
    message: str
    fatigue_level: int
    fatigue_category: str
    uptime_hours: float
    command: str
    mode: str
    override_instruction: Optional[str] = None


class HumsanaInterlock:
    """
    The Cognitive Safety Engine.
    
    Prevents dangerous commands when the user is fatigued,
    with a "Break Glass" protocol for emergencies.
    """
    
    # Override phrase pattern
    OVERRIDE_PATTERN = re.compile(
        r'OVERRIDE\s+SAFETY\s+PROTOCOL:\s*(.+)',
        re.IGNORECASE
    )
    
    def __init__(self):
        self.config = load_config()
        self.tracker = get_activity_tracker()
        self.audit = get_audit_logger()
        self.db = LocalDatabase()
        
        # Pending override state (resets after use)
        self._pending_override_reason: Optional[str] = None
    
    def check_command(self, command: str) -> InterlockResult:
        """
        Check if a command should be allowed.
        
        Returns an InterlockResult with the decision.
        """
        # Get current fatigue status
        current_stress = self._get_current_stress()
        fatigue_status = self.tracker.get_fatigue_status(current_stress)
        
        fatigue_level = fatigue_status['fatigue_level']
        fatigue_category = fatigue_status['fatigue_category']
        uptime_hours = fatigue_status['uptime_hours']
        
        # Check if command is dangerous
        is_dangerous = self._is_dangerous_command(command)
        
        # Check if blocked by fatigue
        should_block = is_dangerous and fatigue_level > self.config.fatigue_threshold
        
        if should_block:
            # Command is dangerous and user is fatigued
            return InterlockResult(
                allowed=False,
                status='blocked',
                message=f"⛔ INTERLOCK ENGAGED: High fatigue detected ({fatigue_level}%). "
                        f"You have been active for {uptime_hours:.1f} hours. "
                        f"Command '{self._truncate(command)}' is blocked for safety.",
                fatigue_level=fatigue_level,
                fatigue_category=fatigue_category,
                uptime_hours=uptime_hours,
                command=command,
                mode=self.config.execution_mode,
                override_instruction=(
                    "To proceed anyway, reply with exactly:\n"
                    "OVERRIDE SAFETY PROTOCOL: [your reason]\n\n"
                    "Example: OVERRIDE SAFETY PROTOCOL: P0 production outage"
                )
            )
        
        # Command is allowed
        return InterlockResult(
            allowed=True,
            status='allowed',
            message=f"✅ Safety check passed. Command is {'safe' if not is_dangerous else 'allowed (low fatigue)'}.",
            fatigue_level=fatigue_level,
            fatigue_category=fatigue_category,
            uptime_hours=uptime_hours,
            command=command,
            mode=self.config.execution_mode
        )
    
    def process_override(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a message contains a valid override.
        
        Returns:
            (is_valid_override, reason)
        """
        match = self.OVERRIDE_PATTERN.search(message)
        if match:
            reason = match.group(1).strip()
            if len(reason) > 0:
                self._pending_override_reason = reason
                return True, reason
            return False, None
        return False, None
    
    def execute_command(
        self, 
        command: str, 
        override_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a command with interlock protection.
        
        This is the main entry point for the MCP tool.
        
        Args:
            command: The shell command to execute
            override_reason: If provided, bypasses the interlock
        
        Returns:
            Dict with status, output, and metadata
        """
        # Get fatigue status
        current_stress = self._get_current_stress()
        fatigue_status = self.tracker.get_fatigue_status(current_stress)
        fatigue_level = fatigue_status['fatigue_level']
        fatigue_category = fatigue_status['fatigue_category']
        uptime_hours = fatigue_status['uptime_hours']
        
        # Check if dangerous
        is_dangerous = self._is_dangerous_command(command)
        should_block = is_dangerous and fatigue_level > self.config.fatigue_threshold
        
        # Handle override
        if should_block and override_reason:
            # User is overriding - log and allow
            self.audit.log_event(
                event='safety_override',
                command=command,
                fatigue_level=fatigue_level,
                fatigue_category=fatigue_category,
                uptime_hours=uptime_hours,
                outcome='executed' if self.config.execution_mode == 'live' else 'simulated',
                mode=self.config.execution_mode,
                override_reason=override_reason,
                webhook_url=self.config.webhook_url
            )
            
            # Execute or simulate
            return self._execute_or_simulate(
                command, 
                fatigue_level, 
                fatigue_category,
                uptime_hours,
                override_reason=override_reason
            )
        
        # Block if dangerous + fatigued + no override
        if should_block:
            self.audit.log_event(
                event='command_blocked',
                command=command,
                fatigue_level=fatigue_level,
                fatigue_category=fatigue_category,
                uptime_hours=uptime_hours,
                outcome='blocked',
                mode=self.config.execution_mode,
                webhook_url=self.config.webhook_url
            )
            
            return {
                'status': 'BLOCKED',
                'error': '⛔ INTERLOCK ENGAGED',
                'message': (
                    f"High fatigue detected ({fatigue_level}%, {fatigue_category}). "
                    f"You have been active for {uptime_hours:.1f} hours.\n\n"
                    f"Command `{self._truncate(command)}` is high-risk and has been blocked.\n\n"
                    f"To proceed, you MUST reply with:\n"
                    f"**OVERRIDE SAFETY PROTOCOL: [reason]**\n\n"
                    f"Example: `OVERRIDE SAFETY PROTOCOL: P0 production incident`"
                ),
                'fatigue': {
                    'level': fatigue_level,
                    'category': fatigue_category,
                    'uptime_hours': uptime_hours
                },
                'mode': self.config.execution_mode,
                'override_required': True
            }
        
        # Safe command or low fatigue - execute or simulate
        if is_dangerous:
            self.audit.log_event(
                event='dangerous_command_allowed',
                command=command,
                fatigue_level=fatigue_level,
                fatigue_category=fatigue_category,
                uptime_hours=uptime_hours,
                outcome='executed' if self.config.execution_mode == 'live' else 'simulated',
                mode=self.config.execution_mode,
                webhook_url=self.config.webhook_url
            )
        
        return self._execute_or_simulate(
            command, 
            fatigue_level, 
            fatigue_category,
            uptime_hours
        )
    
    def _execute_or_simulate(
        self, 
        command: str,
        fatigue_level: int,
        fatigue_category: str,
        uptime_hours: float,
        override_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute command (live mode) or simulate (dry_run mode)."""
        mode = self.config.execution_mode
        
        if mode == 'dry_run':
            return {
                'status': 'SIMULATED',
                'message': (
                    f"✅ [DRY RUN] Safety check passed.\n\n"
                    f"Command: `{command}`\n\n"
                    f"This command WOULD have been executed.\n"
                    f"(Execution skipped: dry_run mode active)\n\n"
                    f"To enable real execution, set `execution_mode: live` in ~/.humsana/config.yaml"
                ),
                'command': command,
                'fatigue': {
                    'level': fatigue_level,
                    'category': fatigue_category,
                    'uptime_hours': uptime_hours
                },
                'mode': 'dry_run',
                'override_reason': override_reason
            }
        
        # Live execution
        try:
            # Check allowlist if configured
            if self.config.allow_patterns:
                if not self._matches_patterns(command, self.config.allow_patterns):
                    return {
                        'status': 'BLOCKED',
                        'error': 'Command not in allowlist',
                        'message': f"Command '{self._truncate(command)}' is not in the allow_patterns list.",
                        'mode': 'live'
                    }
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            return {
                'status': 'EXECUTED',
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': command,
                'fatigue': {
                    'level': fatigue_level,
                    'category': fatigue_category,
                    'uptime_hours': uptime_hours
                },
                'mode': 'live',
                'override_reason': override_reason
            }
        
        except subprocess.TimeoutExpired:
            return {
                'status': 'TIMEOUT',
                'error': 'Command timed out after 30 seconds',
                'command': command,
                'mode': 'live'
            }
        except Exception as e:
            return {
                'status': 'ERROR',
                'error': str(e),
                'command': command,
                'mode': 'live'
            }
    
    def _is_dangerous_command(self, command: str) -> bool:
        """Check if a command matches dangerous patterns."""
        command_lower = command.lower()
        
        # Check hardcoded dangerous commands
        for pattern in self.config.dangerous_commands:
            if pattern.lower() in command_lower:
                return True
        
        # Check user-defined deny patterns
        for pattern in self.config.deny_patterns:
            if pattern.lower() in command_lower:
                return True
        
        return False
    
    def _matches_patterns(self, command: str, patterns: list) -> bool:
        """Check if command matches any pattern in list."""
        command_lower = command.lower()
        for pattern in patterns:
            if pattern.lower() in command_lower:
                return True
        return False
    
    def _get_current_stress(self) -> float:
        """Get current stress level from the daemon's analysis."""
        try:
            metrics = self.db.get_average_metrics(minutes=5)
            return metrics.get('stress_level', 0.0)
        except:
            return 0.0
    
    def _truncate(self, s: str, max_len: int = 50) -> str:
        """Truncate string for display."""
        if len(s) <= max_len:
            return s
        return s[:max_len-3] + '...'
    
    def get_status(self) -> Dict[str, Any]:
        """Get current interlock status."""
        current_stress = self._get_current_stress()
        fatigue_status = self.tracker.get_fatigue_status(current_stress)
        
        return {
            'interlock_active': fatigue_status['fatigue_level'] > self.config.fatigue_threshold,
            'execution_mode': self.config.execution_mode,
            'fatigue': fatigue_status,
            'threshold': self.config.fatigue_threshold,
            'dangerous_patterns_count': len(self.config.dangerous_commands) + len(self.config.deny_patterns),
            'webhook_configured': self.config.webhook_url is not None
        }


# Singleton instance
_interlock: Optional[HumsanaInterlock] = None

def get_interlock() -> HumsanaInterlock:
    """Get the singleton HumsanaInterlock instance."""
    global _interlock
    if _interlock is None:
        _interlock = HumsanaInterlock()
    return _interlock