"""
Humsana Daemon - Local Database
Stores analyzed signals in SQLite (~/.humsana/signals.db)

PRIVACY: Only stores aggregated metrics, never raw keystrokes.
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from .analyzer import AnalysisResult, UserState


def get_db_path() -> Path:
    """Get the path to the local database."""
    humsana_dir = Path.home() / ".humsana"
    humsana_dir.mkdir(exist_ok=True)
    return humsana_dir / "signals.db"


class LocalDatabase:
    """
    Local SQLite database for storing analysis results.
    
    Schema stores ONLY aggregated metrics:
    - Stress/focus/cognitive_load scores
    - User state
    - Recommendations
    
    NEVER stores:
    - Raw keystrokes
    - Key codes or characters
    - Actual typed content
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    
                    -- Core scores (0.0 to 1.0)
                    stress_level REAL NOT NULL,
                    focus_level REAL NOT NULL,
                    cognitive_load REAL NOT NULL,
                    
                    -- Derived state
                    state TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    
                    -- Recommendations
                    response_style TEXT NOT NULL,
                    avoid_clarifying_questions INTEGER NOT NULL,
                    interruptible INTEGER NOT NULL,
                    
                    -- Metrics (for display, not privacy-sensitive)
                    typing_wpm REAL,
                    backspace_ratio REAL,
                    rhythm_variance REAL,
                    idle_seconds REAL
                )
            """)
            
            # Index for fast recent queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON analysis_results(timestamp DESC)
            """)
            
            # Session tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_analyses INTEGER DEFAULT 0,
                    avg_stress REAL,
                    avg_focus REAL,
                    dominant_state TEXT
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def store_analysis(self, result: AnalysisResult) -> int:
        """
        Store an analysis result.
        
        Returns:
            The ID of the inserted row.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO analysis_results (
                    timestamp,
                    stress_level, focus_level, cognitive_load,
                    state, confidence,
                    response_style, avoid_clarifying_questions, interruptible,
                    typing_wpm, backspace_ratio, rhythm_variance, idle_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                result.stress_level,
                result.focus_level,
                result.cognitive_load,
                result.state.value,
                result.confidence,
                result.response_style,
                1 if result.avoid_clarifying_questions else 0,
                1 if result.interruptible else 0,
                result.typing_wpm,
                result.backspace_ratio,
                result.rhythm_variance,
                result.idle_seconds
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_recent_analyses(
        self, 
        count: int = 10,
        minutes: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent analysis results.
        
        Args:
            count: Maximum number of results
            minutes: Only get results from last N minutes
        """
        with self._get_connection() as conn:
            if minutes:
                cursor = conn.execute("""
                    SELECT * FROM analysis_results
                    WHERE timestamp > datetime('now', ?)
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (f'-{minutes} minutes', count))
            else:
                cursor = conn.execute("""
                    SELECT * FROM analysis_results
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (count,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_current_state(self) -> Optional[Dict[str, Any]]:
        """Get the most recent analysis result."""
        results = self.get_recent_analyses(count=1)
        return results[0] if results else None
    
    def get_average_metrics(self, minutes: int = 5) -> Dict[str, float]:
        """
        Get average metrics over the last N minutes.
        This is what the MCP server will expose to Claude.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    AVG(stress_level) as avg_stress,
                    AVG(focus_level) as avg_focus,
                    AVG(cognitive_load) as avg_cognitive_load,
                    AVG(typing_wpm) as avg_wpm,
                    AVG(backspace_ratio) as avg_backspace,
                    COUNT(*) as sample_count
                FROM analysis_results
                WHERE timestamp > datetime('now', ?)
            """, (f'-{minutes} minutes',))
            
            row = cursor.fetchone()
            if row and row['sample_count'] > 0:
                return {
                    "stress_level": round(row['avg_stress'] or 0, 3),
                    "focus_level": round(row['avg_focus'] or 0, 3),
                    "cognitive_load": round(row['avg_cognitive_load'] or 0, 3),
                    "typing_wpm": round(row['avg_wpm'] or 0, 1),
                    "backspace_ratio": round(row['avg_backspace'] or 0, 3),
                    "sample_count": row['sample_count'],
                    "window_minutes": minutes
                }
            
            return {
                "stress_level": 0.0,
                "focus_level": 0.5,
                "cognitive_load": 0.3,
                "typing_wpm": 0.0,
                "backspace_ratio": 0.0,
                "sample_count": 0,
                "window_minutes": minutes
            }
    
    def get_dominant_state(self, minutes: int = 5) -> str:
        """Get the most common state over the last N minutes."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT state, COUNT(*) as count
                FROM analysis_results
                WHERE timestamp > datetime('now', ?)
                GROUP BY state
                ORDER BY count DESC
                LIMIT 1
            """, (f'-{minutes} minutes',))
            
            row = cursor.fetchone()
            return row['state'] if row else 'relaxed'
    
    def start_session(self) -> int:
        """Start a new session and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO sessions (start_time)
                VALUES (?)
            """, (datetime.utcnow().isoformat(),))
            conn.commit()
            return cursor.lastrowid
    
    def end_session(self, session_id: int) -> None:
        """End a session and calculate summary stats."""
        with self._get_connection() as conn:
            # Get session start time
            cursor = conn.execute(
                "SELECT start_time FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if not row:
                return
            
            start_time = row['start_time']
            
            # Calculate session stats
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    AVG(stress_level) as avg_stress,
                    AVG(focus_level) as avg_focus
                FROM analysis_results
                WHERE timestamp >= ?
            """, (start_time,))
            
            stats = cursor.fetchone()
            
            # Get dominant state
            cursor = conn.execute("""
                SELECT state, COUNT(*) as count
                FROM analysis_results
                WHERE timestamp >= ?
                GROUP BY state
                ORDER BY count DESC
                LIMIT 1
            """, (start_time,))
            
            state_row = cursor.fetchone()
            dominant_state = state_row['state'] if state_row else 'relaxed'
            
            # Update session
            conn.execute("""
                UPDATE sessions SET
                    end_time = ?,
                    total_analyses = ?,
                    avg_stress = ?,
                    avg_focus = ?,
                    dominant_state = ?
                WHERE id = ?
            """, (
                datetime.utcnow().isoformat(),
                stats['total'],
                stats['avg_stress'],
                stats['avg_focus'],
                dominant_state,
                session_id
            ))
            conn.commit()
    
    def cleanup_old_data(self, days: int = 7) -> int:
        """
        Delete data older than N days.
        Returns number of rows deleted.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM analysis_results
                WHERE timestamp < datetime('now', ?)
            """, (f'-{days} days',))
            conn.commit()
            return cursor.rowcount