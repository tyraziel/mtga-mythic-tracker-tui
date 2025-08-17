"""
Session-related models for MTGA Manual TUI Tracker.

Contains CompletedSession and SessionStats classes with all session tracking logic.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from .rank import ManualRank, RankTier, FormatType


@dataclass
class CompletedSession:
    """A completed session record."""
    date: str  # YYYY-MM-DD format
    wins: int
    losses: int
    start_time: datetime
    end_time: datetime
    start_rank: Optional[ManualRank] = None
    end_rank: Optional[ManualRank] = None
    format_type: FormatType = FormatType.CONSTRUCTED_BO1
    bar_progress: int = 0  # Net bars gained/lost


@dataclass  
class SessionStats:
    """Session and season statistics."""
    # Current session
    session_wins: int = 0
    session_losses: int = 0
    session_start_time: Optional[datetime] = None
    session_start_rank: Optional[ManualRank] = None
    last_result_time: Optional[datetime] = None
    session_goal_tier: Optional[RankTier] = None
    session_goal_division: Optional[int] = None
    
    # Season totals
    season_wins: int = 0
    season_losses: int = 0
    season_start_rank: Optional[ManualRank] = None
    season_highest_rank: Optional[ManualRank] = None
    season_end_date: Optional[datetime] = None
    
    # Streaks
    current_win_streak: int = 0
    current_loss_streak: int = 0
    best_win_streak: int = 0
    worst_loss_streak: int = 0
    
    # Session history (last 5 sessions)
    session_history: List[CompletedSession] = None
    
    # Game notes for current session
    game_notes: List[dict] = None
    
    # Session game results (for L10 display)
    session_game_results: List[str] = None
    
    # Session timer controls
    session_paused: bool = False
    total_paused_time: float = 0.0  # Total time paused in seconds
    pause_start_time: Optional[datetime] = None
    game_start_time: Optional[datetime] = None
    game_paused_time: float = 0.0  # Total time paused during current game
    game_durations: List[float] = None  # List of completed game durations in seconds
    
    # Milestone tracking (to detect when thresholds are crossed)
    last_session_win_rate: float = 0.0
    last_season_win_rate: float = 0.0
    
    # Paused time since last result (for active time calculation)
    paused_time_since_last_result: float = 0.0
    
    def __post_init__(self):
        """Initialize default values."""
        if self.session_history is None:
            self.session_history = []
        if self.game_durations is None:
            self.game_durations = []
        if not hasattr(self, 'game_notes') or self.game_notes is None:
            self.game_notes = []
        if not hasattr(self, 'session_game_results') or self.session_game_results is None:
            self.session_game_results = []
    
    def get_session_win_rate(self) -> float:
        """Calculate session win rate."""
        total = self.session_wins + self.session_losses
        if total == 0:
            return 0.0
        return (self.session_wins / total) * 100
    
    def get_season_win_rate(self) -> float:
        """Calculate season win rate."""
        total = self.season_wins + self.season_losses
        if total == 0:
            return 0.0
        return (self.season_wins / total) * 100
    
    def add_win(self):
        """Add a win to session and update streaks."""
        self.session_wins += 1
        self.season_wins += 1
        self.current_win_streak += 1
        self.current_loss_streak = 0
        self.best_win_streak = max(self.best_win_streak, self.current_win_streak)
        self.last_result_time = datetime.now()
        # Reset paused time counter for last result tracking
        self.paused_time_since_last_result = 0.0
        
        # Track all session game results
        if not hasattr(self, 'session_game_results') or self.session_game_results is None:
            self.session_game_results = []
        self.session_game_results.append('W')
        # Keep ALL results for the session (don't limit to 10)
    
    def add_loss(self):
        """Add a loss to session and update streaks."""
        self.session_losses += 1
        self.season_losses += 1
        self.current_loss_streak += 1
        self.current_win_streak = 0
        self.worst_loss_streak = max(self.worst_loss_streak, self.current_loss_streak)
        self.last_result_time = datetime.now()
        # Reset paused time counter for last result tracking
        self.paused_time_since_last_result = 0.0
        
        # Track all session game results
        if not hasattr(self, 'session_game_results') or self.session_game_results is None:
            self.session_game_results = []
        self.session_game_results.append('L')
        # Keep ALL results for the session (don't limit to 10)
    
    def complete_current_session(self, current_rank: ManualRank, current_format: FormatType):
        """Complete the current session and add it to history."""
        if self.session_start_time and (self.session_wins > 0 or self.session_losses > 0):
            # Calculate bar progress
            bar_progress = self._calculate_bar_progress(self.session_start_rank, current_rank)
            
            # Create completed session record
            completed = CompletedSession(
                date=datetime.now().strftime("%Y-%m-%d"),
                wins=self.session_wins,
                losses=self.session_losses,
                start_time=self.session_start_time,
                end_time=datetime.now(),
                start_rank=self.session_start_rank,
                end_rank=current_rank,
                format_type=current_format,
                bar_progress=bar_progress
            )
            
            # Add to history (keep only last 5)
            self.session_history.append(completed)
            if len(self.session_history) > 5:
                self.session_history = self.session_history[-5:]
    
    def _calculate_bar_progress(self, start_rank: Optional[ManualRank], end_rank: ManualRank) -> int:
        """Calculate net bar progress between two ranks."""
        if not start_rank:
            return 0
        
        # This is a simplified calculation - would need full rank-to-bars conversion
        # For now, just estimate based on tier/division/pips differences
        try:
            start_total = self._rank_to_total_bars(start_rank)
            end_total = self._rank_to_total_bars(end_rank)
            return end_total - start_total
        except:
            return 0
    
    def _rank_to_total_bars(self, rank: ManualRank) -> int:
        """Convert rank to total bars for comparison."""
        tier_values = {"Bronze": 0, "Silver": 24, "Gold": 48, "Platinum": 72, "Diamond": 96, "Mythic": 120}
        tier_name = rank.tier.value if hasattr(rank.tier, 'value') else str(rank.tier)
        
        if rank.is_mythic():
            return 120
        
        base_bars = tier_values.get(tier_name, 0)
        division_bars = (4 - rank.division) * 6  # Division 4=0 bars, 3=6 bars, 2=12 bars, 1=18 bars
        pip_bars = rank.pips
        
        return base_bars + division_bars + pip_bars
    
    def start_game_timer(self):
        """Start timing a new game."""
        self.game_start_time = datetime.now()
        self.game_paused_time = 0.0
    
    def end_game_timer(self) -> float:
        """End the current game timer and return duration."""
        if not self.game_start_time:
            return 0.0
        
        # Calculate total game duration excluding pauses
        total_elapsed = (datetime.now() - self.game_start_time).total_seconds()
        game_duration = total_elapsed - self.game_paused_time
        
        # Record the duration
        self.game_durations.append(max(0, game_duration))
        
        # Keep only last 50 games for average calculation
        if len(self.game_durations) > 50:
            self.game_durations = self.game_durations[-50:]
        
        # Reset game timer
        self.game_start_time = None
        self.game_paused_time = 0.0
        
        return game_duration
    
    def get_current_game_duration(self) -> float:
        """Get current game duration in seconds."""
        if not self.game_start_time:
            return 0.0
        
        total_elapsed = (datetime.now() - self.game_start_time).total_seconds()
        return max(0, total_elapsed - self.game_paused_time)
    
    def get_average_game_duration(self) -> float:
        """Get average game duration in seconds."""
        if not self.game_durations:
            return 0.0
        return sum(self.game_durations) / len(self.game_durations)
    
    def pause_session(self):
        """Pause both session and game timers."""
        if not self.session_paused and self.session_start_time:
            self.session_paused = True
            self.pause_start_time = datetime.now()
    
    def resume_session(self):
        """Resume both session and game timers."""
        if self.session_paused and self.pause_start_time:
            # Calculate pause duration (handle string datetime conversion)
            try:
                if isinstance(self.pause_start_time, str):
                    pause_start = datetime.fromisoformat(self.pause_start_time)
                else:
                    pause_start = self.pause_start_time
                
                pause_duration = (datetime.now() - pause_start).total_seconds()
            except:
                # If there's any issue with datetime conversion, just reset
                pause_duration = 0.0
            
            # Add to session paused time
            self.total_paused_time += pause_duration
            
            # Add to current game paused time if game is active
            if self.game_start_time:
                self.game_paused_time += pause_duration
            
            # Add to paused time since last result
            self.paused_time_since_last_result += pause_duration
            
            self.session_paused = False
            self.pause_start_time = None
    
    def get_active_session_duration(self) -> timedelta:
        """Get session duration excluding paused time."""
        if not self.session_start_time:
            return timedelta(0)
        
        # Calculate total elapsed time
        total_elapsed = datetime.now() - self.session_start_time
        
        # Subtract total paused time
        current_pause_time = 0
        if self.session_paused and self.pause_start_time:
            try:
                if isinstance(self.pause_start_time, str):
                    pause_start = datetime.fromisoformat(self.pause_start_time)
                else:
                    pause_start = self.pause_start_time
                current_pause_time = (datetime.now() - pause_start).total_seconds()
            except:
                current_pause_time = 0
        
        active_seconds = total_elapsed.total_seconds() - self.total_paused_time - current_pause_time
        return timedelta(seconds=max(0, active_seconds))
    
    def get_time_since_last_result(self) -> Tuple[int, int]:
        """Get time since last result as (real_seconds, active_seconds)."""
        if not self.last_result_time:
            return (0, 0)
        
        # Real time (wall clock)
        real_elapsed = (datetime.now() - self.last_result_time).total_seconds()
        
        # Active time (excluding pauses)
        current_pause_time = 0
        if self.session_paused and self.pause_start_time:
            try:
                if isinstance(self.pause_start_time, str):
                    pause_start = datetime.fromisoformat(self.pause_start_time)
                else:
                    pause_start = self.pause_start_time
                current_pause_time = (datetime.now() - pause_start).total_seconds()
            except:
                current_pause_time = 0
        
        active_elapsed = real_elapsed - self.paused_time_since_last_result - current_pause_time
        
        return (int(real_elapsed), int(max(0, active_elapsed)))
    
    def reset_session(self, current_rank: Optional[ManualRank] = None):
        """Reset session stats but keep season totals."""
        self.session_wins = 0
        self.session_losses = 0
        self.session_start_time = datetime.now()
        self.session_start_rank = current_rank
        self.current_win_streak = 0
        self.current_loss_streak = 0
        # Reset timer controls
        self.session_paused = False
        self.total_paused_time = 0.0
        self.pause_start_time = None
        # Reset game timer (but keep duration history for averages)
        self.game_start_time = None
        self.game_paused_time = 0.0
        # Reset milestone tracking
        self.last_session_win_rate = 0.0
        # Reset last result tracking
        self.last_result_time = None
        self.paused_time_since_last_result = 0.0
        # Reset L10 game results for new session
        self.session_game_results = []