"""
Humsana Daemon - Signal Analyzer v2
Converts raw timing signals into stress/focus/cognitive_load scores.

v2.0 UPGRADE: Adds ADRENALINE and FATIGUED states
- ADRENALINE: High speed + Low errors = "In the zone" / P0 incident mode
- FATIGUED: High errors + High cognitive load = Dangerous, should block

The Signal Library (mapping from physics to psychology) is our core IP.
These thresholds were calibrated through research and testing.
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import statistics

from .collector import SignalSnapshot


class UserState(Enum):
    """Detected user state."""
    RELAXED = "relaxed"
    WORKING = "working"
    FOCUSED = "focused"
    STRESSED = "stressed"
    DEBUGGING = "debugging"  # High stress + high activity
    FATIGUED = "fatigued"    # High errors, slow/erratic - DANGEROUS
    ADRENALINE = "adrenaline" # High speed, high accuracy - P0/Flow state


@dataclass
class AnalysisResult:
    """Result of analyzing behavioral signals."""
    # Core scores (0.0 to 1.0)
    stress_level: float
    focus_level: float
    cognitive_load: float
    
    # Derived state
    state: UserState
    
    # Confidence in this analysis (based on signal count)
    confidence: float
    
    # Recommendations for AI
    response_style: str  # "concise" | "detailed" | "friendly" | "protective" | "concise_command_mode"
    avoid_clarifying_questions: bool
    interruptible: bool
    
    # Raw metrics (for debugging/display)
    typing_wpm: float
    backspace_ratio: float
    rhythm_variance: float
    idle_seconds: float


class SignalAnalyzer:
    """
    Analyzes behavioral signals to infer user state.
    
    v2.0: Enhanced state detection with Adrenaline vs Fatigue distinction
    
    THE SIGNAL LIBRARY (our moat):
    These mappings from raw signals to psychological state
    are the result of behavioral research and calibration.
    """
    
    # Thresholds (calibrated values)
    STRESS_THRESHOLDS = {
        "high_wpm": 80,           # Words per minute indicating stress
        "high_backspace": 0.15,   # >15% corrections = anxiety
        "high_variance": 10000,   # High rhythm variance = erratic
    }
    
    FOCUS_THRESHOLDS = {
        "sustained_typing": 30,   # Seconds of continuous typing
        "low_variance": 3000,     # Consistent rhythm = flow state
        "no_idle": 5,             # No pause > 5 seconds
    }
    
    # NEW: Adrenaline detection thresholds
    ADRENALINE_THRESHOLDS = {
        "min_wpm": 90,            # Must be typing fast
        "max_backspace": 0.05,   # But with very few errors
        "min_focus": 0.7,         # And high focus
    }
    
    # NEW: Fatigue detection thresholds
    FATIGUE_THRESHOLDS = {
        "min_backspace": 0.15,   # High error rate
        "min_cognitive_load": 0.8, # High cognitive load
    }
    
    def __init__(self):
        # History for temporal analysis
        self.analysis_history: List[AnalysisResult] = []
    
    def analyze(
        self, 
        signals: List[SignalSnapshot],
        idle_seconds: float = 0.0
    ) -> AnalysisResult:
        """
        Analyze a batch of signals and return user state.
        
        Args:
            signals: Recent SignalSnapshot objects
            idle_seconds: Seconds since last activity
        
        Returns:
            AnalysisResult with scores and recommendations
        """
        
        # Need minimum signals for reliable analysis
        if len(signals) < 10:
            return self._create_default_result(
                confidence=0.1,
                idle_seconds=idle_seconds
            )
        
        # Calculate raw metrics
        typing_wpm = self._calculate_wpm(signals)
        backspace_ratio = self._calculate_backspace_ratio(signals)
        rhythm_variance = self._calculate_rhythm_variance(signals)
        
        # Calculate core scores
        stress_level = self._calculate_stress(
            typing_wpm, backspace_ratio, rhythm_variance
        )
        focus_level = self._calculate_focus(
            signals, rhythm_variance, idle_seconds
        )
        cognitive_load = self._calculate_cognitive_load(
            typing_wpm, backspace_ratio, rhythm_variance
        )
        
        # Determine state (v2: with Adrenaline/Fatigue detection)
        state = self._determine_state(
            stress_level, focus_level, cognitive_load,
            typing_wpm, backspace_ratio, idle_seconds
        )
        
        # Calculate confidence based on signal count
        confidence = min(len(signals) / 100, 1.0)
        
        # Generate recommendations (v2: updated for new states)
        response_style, avoid_questions, interruptible = self._generate_recommendations(
            stress_level, focus_level, state
        )
        
        result = AnalysisResult(
            stress_level=stress_level,
            focus_level=focus_level,
            cognitive_load=cognitive_load,
            state=state,
            confidence=confidence,
            response_style=response_style,
            avoid_clarifying_questions=avoid_questions,
            interruptible=interruptible,
            typing_wpm=typing_wpm,
            backspace_ratio=backspace_ratio,
            rhythm_variance=rhythm_variance,
            idle_seconds=idle_seconds
        )
        
        # Store in history
        self.analysis_history.append(result)
        if len(self.analysis_history) > 100:
            self.analysis_history.pop(0)
        
        return result
    
    def _calculate_wpm(self, signals: List[SignalSnapshot]) -> float:
        """
        Estimate words per minute from keystroke intervals.
        Average word = 5 characters.
        """
        if len(signals) < 2:
            return 0.0
        
        # Total time span
        time_span = signals[-1].timestamp - signals[0].timestamp
        if time_span <= 0:
            return 0.0
        
        # Characters per second → words per minute
        chars_per_second = len(signals) / time_span
        wpm = (chars_per_second / 5) * 60
        
        return round(wpm, 1)
    
    def _calculate_backspace_ratio(self, signals: List[SignalSnapshot]) -> float:
        """
        Calculate ratio of backspaces to total keystrokes.
        High ratio = anxiety, perfectionism, or debugging.
        """
        if not signals:
            return 0.0
        
        backspace_count = sum(1 for s in signals if s.is_backspace)
        return backspace_count / len(signals)
    
    def _calculate_rhythm_variance(self, signals: List[SignalSnapshot]) -> float:
        """
        Calculate variance in inter-keystroke intervals.
        High variance = erratic, stressed, uncertain.
        Low variance = flow state, confident.
        """
        intervals = [s.interval_ms for s in signals if s.interval_ms > 0 and s.interval_ms < 2000]
        
        if len(intervals) < 2:
            return 0.0
        
        try:
            return statistics.variance(intervals)
        except statistics.StatisticsError:
            return 0.0
    
    def _calculate_stress(
        self, 
        wpm: float, 
        backspace_ratio: float, 
        variance: float
    ) -> float:
        """
        Calculate stress score (0.0 to 1.0).
        
        Stress indicators:
        - High typing velocity (rushing)
        - High backspace ratio (corrections/anxiety)
        - High rhythm variance (erratic behavior)
        """
        stress = 0.0
        
        # High WPM indicates rushing/stress
        if wpm > self.STRESS_THRESHOLDS["high_wpm"]:
            stress += 0.35
        elif wpm > 60:
            stress += 0.15
        
        # High backspace ratio indicates anxiety/perfectionism
        if backspace_ratio > self.STRESS_THRESHOLDS["high_backspace"]:
            stress += 0.35
        elif backspace_ratio > 0.10:
            stress += 0.15
        
        # High variance indicates erratic behavior
        if variance > self.STRESS_THRESHOLDS["high_variance"]:
            stress += 0.30
        elif variance > 5000:
            stress += 0.15
        
        return min(stress, 1.0)
    
    def _calculate_focus(
        self, 
        signals: List[SignalSnapshot],
        variance: float,
        idle_seconds: float
    ) -> float:
        """
        Calculate focus score (0.0 to 1.0).
        
        Focus indicators:
        - Sustained typing (no long pauses)
        - Low rhythm variance (consistent flow)
        - Recent activity (not idle)
        """
        focus = 0.5  # Start neutral
        
        # Check for sustained typing
        if len(signals) >= 50:
            time_span = signals[-1].timestamp - signals[0].timestamp
            if time_span > self.FOCUS_THRESHOLDS["sustained_typing"]:
                focus += 0.25
        
        # Low variance = flow state
        if variance < self.FOCUS_THRESHOLDS["low_variance"]:
            focus += 0.25
        elif variance < 5000:
            focus += 0.10
        
        # Penalize for being idle
        if idle_seconds > 60:
            focus -= 0.30
        elif idle_seconds > 30:
            focus -= 0.15
        elif idle_seconds > self.FOCUS_THRESHOLDS["no_idle"]:
            focus -= 0.05
        
        return max(0.0, min(focus, 1.0))
    
    def _calculate_cognitive_load(
        self,
        wpm: float,
        backspace_ratio: float,
        variance: float
    ) -> float:
        """
        Calculate cognitive load (0.0 to 1.0).
        
        High cognitive load = user is overwhelmed, needs simpler responses.
        """
        load = 0.3  # Baseline
        
        # High WPM + high backspace = problem-solving under pressure
        if wpm > 70 and backspace_ratio > 0.12:
            load += 0.35
        
        # High variance alone indicates task-switching
        if variance > 8000:
            load += 0.25
        
        # Very fast typing with corrections = debugging
        if wpm > 90 and backspace_ratio > 0.18:
            load += 0.20
        
        return min(load, 1.0)
    
    def _determine_state(
        self,
        stress: float,
        focus: float,
        cognitive_load: float,
        wpm: float,
        backspace_ratio: float,
        idle_seconds: float
    ) -> UserState:
        """
        Map scores to a discrete user state.
        
        v2.0: Added ADRENALINE and FATIGUED detection
        
        Key insight from friend:
        - ADRENALINE: High speed + LOW errors = "In the zone" or P0 mode → DON'T block
        - FATIGUED: High load + HIGH errors = Sloppy, dangerous → BLOCK
        """
        
        # Check for idle/relaxed first
        if idle_seconds > 120:
            return UserState.RELAXED
        
        # NEW: ADRENALINE detection (High speed + Low errors + High focus)
        # This is the "P0 incident" or "Flow state" signature
        # We should NOT block commands in this state
        if (wpm > self.ADRENALINE_THRESHOLDS["min_wpm"] and 
            backspace_ratio < self.ADRENALINE_THRESHOLDS["max_backspace"] and
            focus > self.ADRENALINE_THRESHOLDS["min_focus"]):
            return UserState.ADRENALINE
        
        # NEW: FATIGUED detection (High load + High errors)
        # This is the "sloppy, dangerous" signature
        # We SHOULD block commands in this state
        if (cognitive_load > self.FATIGUE_THRESHOLDS["min_cognitive_load"] and
            backspace_ratio > self.FATIGUE_THRESHOLDS["min_backspace"]):
            return UserState.FATIGUED
        
        # High stress + high activity = debugging
        if stress > 0.7 and cognitive_load > 0.6:
            return UserState.DEBUGGING
        
        # High stress
        if stress > 0.6:
            return UserState.STRESSED
        
        # High focus, low stress = deep work
        if focus > 0.7 and stress < 0.4:
            return UserState.FOCUSED
        
        # Moderate focus = working
        if focus > 0.4:
            return UserState.WORKING
        
        # Low everything = relaxed
        return UserState.RELAXED
    
    def _generate_recommendations(
        self,
        stress: float,
        focus: float,
        state: UserState
    ) -> tuple[str, bool, bool]:
        """
        Generate recommendations for AI interaction.
        
        v2.0: Updated for ADRENALINE and FATIGUED states
        
        Returns:
            (response_style, avoid_clarifying_questions, interruptible)
        """
        
        # NEW: Adrenaline mode - user is "in the zone" or handling P0
        # Be extremely concise, no chatter, just execute
        if state == UserState.ADRENALINE:
            return ("concise_command_mode", True, False)
        
        # NEW: Fatigued mode - user is making mistakes
        # Be protective, double-check things, add friction
        if state == UserState.FATIGUED:
            return ("protective", True, False)
        
        if state == UserState.DEBUGGING:
            # User is problem-solving under pressure
            return ("concise", True, False)
        
        if state == UserState.STRESSED:
            # User is stressed - be brief and direct
            return ("concise", True, False)
        
        if state == UserState.FOCUSED:
            # User is in flow - don't interrupt unnecessarily
            return ("detailed", False, False)
        
        if state == UserState.WORKING:
            # Normal working mode
            return ("detailed", False, True)
        
        # Relaxed - full engagement OK
        return ("friendly", False, True)
    
    def _create_default_result(
        self,
        confidence: float,
        idle_seconds: float
    ) -> AnalysisResult:
        """Create a default result when we don't have enough data."""
        return AnalysisResult(
            stress_level=0.0,
            focus_level=0.5,
            cognitive_load=0.3,
            state=UserState.RELAXED,
            confidence=confidence,
            response_style="friendly",
            avoid_clarifying_questions=False,
            interruptible=True,
            typing_wpm=0.0,
            backspace_ratio=0.0,
            rhythm_variance=0.0,
            idle_seconds=idle_seconds
        )