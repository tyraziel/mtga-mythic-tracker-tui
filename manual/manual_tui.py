#!/usr/bin/env python3
"""
MTGA Mythic TUI Session Tracker (Manual) - Standalone Version
Complete manual rank tracking with no external dependencies.
"""

import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Union, Tuple
from enum import Enum
import asyncio
import os
from dataclasses import dataclass, asdict

from textual.app import App, ComposeResult
from textual.widgets import Static, Input, Button, Label, Footer, Select, TextArea, DataTable
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message

# === MODELS ===

class FormatType(str, Enum):
    """MTG Arena format types."""
    CONSTRUCTED_BO1 = "Constructed BO1"
    CONSTRUCTED_BO3 = "Constructed BO3" 
    LIMITED = "Limited"

class RankTier(str, Enum):
    """MTG Arena rank tiers."""
    BRONZE = "Bronze"
    SILVER = "Silver"
    GOLD = "Gold"  
    PLATINUM = "Platinum"
    DIAMOND = "Diamond"
    MYTHIC = "Mythic"

@dataclass
class ManualRank:
    """Represents a player's rank in MTG Arena - standalone version."""
    tier: RankTier
    division: Optional[int] = None  # 1-4 for non-Mythic, None for Mythic
    pips: int = 0  # Current pips in division
    mythic_percentage: Optional[float] = None  # For Mythic only
    mythic_rank: Optional[int] = None  # Mythic rank number (#1234)
    format_type: FormatType = FormatType.CONSTRUCTED_BO1
    
    @property
    def max_pips(self) -> int:
        """Get max pips per division based on format."""
        if self.format_type in [FormatType.CONSTRUCTED_BO1, FormatType.CONSTRUCTED_BO3]:
            return 6
        else:  # LIMITED
            return 4
    
    def is_mythic(self) -> bool:
        """Check if rank is Mythic tier."""
        return self.tier == RankTier.MYTHIC
        
    def get_total_bars_remaining_to_mythic(self) -> int:
        """Calculate total bars needed to reach Mythic."""
        if self.is_mythic():
            return 0
            
        # Bars remaining in current division
        bars_in_current = self.max_pips - self.pips
        
        # Bars in divisions above current (within tier)
        bars_in_tier = 0
        if self.division and self.division > 1:
            bars_in_tier = (self.division - 1) * self.max_pips
            
        # Bars in tiers above current
        tier_order = list(RankTier)[:-1]  # Exclude Mythic
        current_tier_idx = tier_order.index(self.tier)
        bars_in_higher_tiers = 0
        
        for tier_idx in range(current_tier_idx + 1, len(tier_order)):
            bars_in_higher_tiers += 4 * self.max_pips  # 4 divisions per tier
            
        return bars_in_current + bars_in_tier + bars_in_higher_tiers
    
    def set_to_position(self, tier: RankTier, division: Optional[int], pips: int) -> 'ManualRank':
        """Set rank to specific position - returns new rank instance."""
        if tier == RankTier.MYTHIC:
            return ManualRank(
                tier=RankTier.MYTHIC,
                mythic_percentage=self.mythic_percentage or 50.0,
                mythic_rank=self.mythic_rank,
                format_type=self.format_type
            )
        else:
            return ManualRank(
                tier=tier,
                division=division,
                pips=pips,
                format_type=self.format_type
            )
    
    def add_win(self) -> 'ManualRank':
        """Add a win (pips based on tier and format)."""
        if self.is_mythic():
            return self  # Mythic doesn't change pips
            
        # Determine pips gained per win based on tier and format
        if self.format_type == FormatType.CONSTRUCTED_BO3:
            # BO3 is double the pips of BO1
            if self.tier in [RankTier.BRONZE, RankTier.SILVER]:
                pips_gained = 4  # Double of 2
            elif self.tier == RankTier.GOLD:
                pips_gained = 4  # Double of 2
            elif self.tier in [RankTier.PLATINUM, RankTier.DIAMOND]:
                pips_gained = 2  # Double of 1
            else:
                pips_gained = 2
        else:
            # BO1 or Limited - standard progression
            if self.tier in [RankTier.BRONZE, RankTier.SILVER]:
                pips_gained = 2
            elif self.tier == RankTier.GOLD:
                pips_gained = 2  
            elif self.tier in [RankTier.PLATINUM, RankTier.DIAMOND]:
                pips_gained = 1
            else:
                pips_gained = 1
            
        new_pips = self.pips + pips_gained
        new_division = self.division
        new_tier = self.tier
        
        # Handle promotion within tier
        while new_pips >= self.max_pips and new_division and new_division > 1:
            new_pips -= self.max_pips
            new_division -= 1
        
        # Handle tier promotion
        if new_pips >= self.max_pips and new_division == 1:
            tier_order = list(RankTier)
            current_index = tier_order.index(self.tier)
            if current_index < len(tier_order) - 1:
                new_tier = tier_order[current_index + 1]
                if new_tier == RankTier.MYTHIC:
                    return ManualRank(
                        tier=RankTier.MYTHIC,
                        mythic_percentage=95.0,
                        format_type=self.format_type
                    )
                else:
                    new_division = 4
                    new_pips = new_pips - self.max_pips  # Carry over extra pips
        
        return ManualRank(
            tier=new_tier,
            division=new_division,
            pips=min(new_pips, self.max_pips),
            format_type=self.format_type
        )
    
    def add_loss(self) -> 'ManualRank':
        """Add a loss (pips lost based on tier)."""
        if self.is_mythic():
            return self  # Mythic doesn't lose pips
            
        # Bronze/Silver can't lose pips at all
        if self.tier in [RankTier.BRONZE, RankTier.SILVER]:
            return self
            
        # Determine pips lost per loss based on format
        if self.format_type == FormatType.CONSTRUCTED_BO3:
            pips_lost = 2  # Double pip loss for BO3
        else:
            pips_lost = 1  # Standard pip loss for BO1/Limited
            
        new_pips = self.pips - pips_lost
        new_division = self.division
        new_tier = self.tier
        
        # Handle demotion if we go below 0 pips
        if new_pips < 0 and new_division and new_division < 4:
            # Move to next division down (higher number)
            new_division += 1
            new_pips = self.max_pips - 1
        elif new_pips < 0 and new_division == 4:
            # At bottom of tier, all tiers have tier floor protection
            if self.tier in [RankTier.BRONZE, RankTier.SILVER, RankTier.GOLD, RankTier.PLATINUM, RankTier.DIAMOND]:
                # All tiers have tier floor - can't drop to previous tier
                new_pips = 0
            else:
                # This shouldn't happen with current tier system
                new_pips = 0
        elif new_pips < 0:
            # Safety check
            new_pips = 0
        
        return ManualRank(
            tier=new_tier,
            division=new_division,
            pips=new_pips,
            format_type=self.format_type
        )
    
    def is_boss_fight(self) -> bool:
        """Check if the next win would promote to the next tier (boss fight!)."""
        if self.is_mythic():
            return False  # Already at highest tier
        
        # Boss fight: Division 1 with max_pips - 1 pips (5/6 pips = next win promotes)
        return self.division == 1 and self.pips == (self.max_pips - 1)
    
    def next_tier(self) -> Optional[str]:
        """Get the name of the next tier for promotion."""
        if self.is_mythic():
            return None
        
        tier_order = list(RankTier)
        current_index = tier_order.index(self.tier)
        if current_index < len(tier_order) - 1:
            next_tier_enum = tier_order[current_index + 1]
            return next_tier_enum.value if hasattr(next_tier_enum, 'value') else str(next_tier_enum)
        return None
    
    def __str__(self) -> str:
        """String representation of rank."""
        if self.is_mythic():
            if self.mythic_rank:
                return f"Mythic #{self.mythic_rank}"
            return f"Mythic {self.mythic_percentage:.1f}%" if self.mythic_percentage else "Mythic"
        tier_name = self.tier.value if hasattr(self.tier, 'value') else self.tier
        return f"{tier_name} {self.division} ({self.pips}/{self.max_pips})"

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
class FormatStats:
    """Statistics for a specific format (Constructed BO1/BO3/Limited)."""
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
    
    # Streaks
    current_win_streak: int = 0
    current_loss_streak: int = 0
    best_win_streak: int = 0
    worst_loss_streak: int = 0
    
    # Session history (last 5 sessions)
    session_history: List[CompletedSession] = None
    
    # Game notes for current session
    game_notes: List[dict] = None
    
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
        if self.session_history is None:
            self.session_history = []
        if self.game_durations is None:
            self.game_durations = []
        if not hasattr(self, 'game_notes') or self.game_notes is None:
            self.game_notes = []
    
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
        if not hasattr(self, 'game_notes') or self.game_notes is None:
            self.game_notes = []
    
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

@dataclass
class AppData:
    """Complete application state."""
    constructed_rank: ManualRank
    limited_rank: ManualRank
    current_format: FormatType
    stats: SessionStats
    show_mythic_progress: bool = True
    collapsed_tiers: List[RankTier] = None
    hidden_tiers: List[RankTier] = None
    auto_collapse_mode: bool = False
    auto_hide_mode: bool = False
    
    def __post_init__(self):
        if self.collapsed_tiers is None:
            self.collapsed_tiers = []
        if self.hidden_tiers is None:
            self.hidden_tiers = []
    
    def get_current_rank(self) -> ManualRank:
        """Get rank for current format."""
        if self.current_format in [FormatType.CONSTRUCTED_BO1, FormatType.CONSTRUCTED_BO3]:
            return self.constructed_rank
        else:
            return self.limited_rank
    
    def set_current_rank(self, rank: ManualRank):
        """Set rank for current format."""
        if self.current_format in [FormatType.CONSTRUCTED_BO1, FormatType.CONSTRUCTED_BO3]:
            self.constructed_rank = rank
        else:
            self.limited_rank = rank
        
        # Clean up hide/collapse states when rank changes
        self._cleanup_tier_states(rank)
    
    def _cleanup_tier_states(self, current_rank: ManualRank):
        """Clean up invalid hide/collapse states and auto-collapse/hide newly completed tiers."""
        tier_order = list(RankTier)[:-1]  # Exclude Mythic
        
        if current_rank.is_mythic():
            # At mythic, all non-mythic tiers are completed
            # If we're in collapse/hide mode, apply to all completed tiers
            if self.collapsed_tiers:
                for tier in tier_order:
                    if tier not in self.collapsed_tiers:
                        self.collapsed_tiers.append(tier)
            if self.hidden_tiers:
                for tier in tier_order:
                    if tier not in self.hidden_tiers:
                        self.hidden_tiers.append(tier)
            return
        
        current_tier_idx = tier_order.index(current_rank.tier)
        completed_tiers = tier_order[:current_tier_idx]  # Tiers below current
        incomplete_tiers = tier_order[current_tier_idx:]  # Current tier and above
        
        # Remove any incomplete tiers from collapsed/hidden lists
        for tier in incomplete_tiers:
            if tier in self.collapsed_tiers:
                self.collapsed_tiers.remove(tier)
            if tier in self.hidden_tiers:
                self.hidden_tiers.remove(tier)
        
        # Auto-collapse/hide newly completed tiers if in auto mode
        if self.auto_collapse_mode:
            for tier in completed_tiers:
                if tier not in self.collapsed_tiers:
                    self.collapsed_tiers.append(tier)
        
        if self.auto_hide_mode:
            for tier in completed_tiers:
                if tier not in self.hidden_tiers:
                    self.hidden_tiers.append(tier)

# === STATE PERSISTENCE ===

class StateManager:
    """Handles saving/loading application state."""
    
    def __init__(self, data_dir: Optional[Path] = None, save_enabled: bool = True):
        self.save_enabled = save_enabled
        
        if data_dir:
            self.data_dir = data_dir
        else:
            # Default location
            home = Path.home()
            if os.name == 'nt':  # Windows
                self.data_dir = home / "AppData" / "Roaming" / "mtga-manual-tracker"
            else:  # Linux/Mac
                self.data_dir = home / ".local" / "share" / "mtga-manual-tracker"
        
        if self.save_enabled:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.state_file = self.data_dir / "tracker_state.json"
    
    def load_state(self) -> AppData:
        """Load application state from file or create default."""
        if not self.save_enabled or not self.state_file.exists():
            return self._create_default_state()
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            # Convert datetime strings back to objects
            self._deserialize_datetimes(data)
            
            # Migrate old format values to new BO1/BO3 system
            self._migrate_format_values(data)
            
            # Reconstruct objects
            constructed_rank = ManualRank(**data['constructed_rank'])
            limited_rank = ManualRank(**data['limited_rank'])
            
            # Handle SessionStats with potential missing fields
            stats_data = data['stats']
            
            # Reconstruct CompletedSession objects from session_history
            if 'session_history' in stats_data and stats_data['session_history']:
                session_history = []
                for session_dict in stats_data['session_history']:
                    session_history.append(CompletedSession(**session_dict))
                stats_data['session_history'] = session_history
            
            stats = SessionStats(**stats_data)
            
            return AppData(
                constructed_rank=constructed_rank,
                limited_rank=limited_rank,
                current_format=FormatType(data['current_format']),
                stats=stats,
                show_mythic_progress=data.get('show_mythic_progress', True),
                collapsed_tiers=[RankTier(t) for t in data.get('collapsed_tiers', [])],
                hidden_tiers=[RankTier(t) for t in data.get('hidden_tiers', [])],
                auto_collapse_mode=data.get('auto_collapse_mode', False),
                auto_hide_mode=data.get('auto_hide_mode', False)
            )
            
        except Exception as e:
            print(f"Error loading state: {e}")
            return self._create_default_state()
    
    def save_state(self, app_data: AppData):
        """Save application state to file."""
        if not self.save_enabled:
            return
        
        try:
            # Convert to serializable format
            data = {
                'constructed_rank': asdict(app_data.constructed_rank),
                'limited_rank': asdict(app_data.limited_rank),
                'current_format': app_data.current_format.value,
                'stats': asdict(app_data.stats),
                'show_mythic_progress': app_data.show_mythic_progress,
                'collapsed_tiers': [t.value for t in app_data.collapsed_tiers],
                'hidden_tiers': [t.value for t in app_data.hidden_tiers],
                'auto_collapse_mode': app_data.auto_collapse_mode,
                'auto_hide_mode': app_data.auto_hide_mode
            }
            
            # Serialize datetime objects
            self._serialize_datetimes(data)
            
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def _create_default_state(self) -> AppData:
        """Create default application state."""
        default_date = datetime.now() + timedelta(days=30)  # 30 days from now
        
        return AppData(
            constructed_rank=ManualRank(
                tier=RankTier.BRONZE,
                division=4,
                pips=0,
                format_type=FormatType.CONSTRUCTED_BO1
            ),
            limited_rank=ManualRank(
                tier=RankTier.BRONZE,
                division=4, 
                pips=0,
                format_type=FormatType.LIMITED
            ),
            current_format=FormatType.CONSTRUCTED_BO1,
            stats=SessionStats(
                session_start_time=datetime.now(),
                season_end_date=default_date
            )
        )
    
    def _serialize_datetimes(self, data: dict):
        """Convert datetime objects to ISO strings for JSON serialization."""
        def convert_datetime(obj):
            if isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            else:
                return obj
        
        # Update the data in place
        for key, value in data.items():
            data[key] = convert_datetime(value)
    
    def _deserialize_datetimes(self, data: dict):
        """Convert ISO strings back to datetime objects."""
        datetime_fields = [
            'session_start_time', 'season_end_date', 'last_result_time',
            'pause_start_time', 'game_start_time',  # Timer datetime fields
            'start_time', 'end_time',  # For CompletedSession objects
            'timestamp'  # For game_notes timestamps
        ]
        
        def convert_iso_string(obj, parent_key=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    obj[k] = convert_iso_string(v, k)
                return obj
            elif isinstance(obj, str) and parent_key in datetime_fields:
                try:
                    return datetime.fromisoformat(obj)
                except:
                    return None
            return obj
        
        for key, value in data.items():
            data[key] = convert_iso_string(value, key)
    
    def _migrate_format_values(self, data):
        """Migrate old format enum values to new BO1/BO3 system."""
        # Migrate current_format
        if data.get('current_format') == 'Constructed':
            data['current_format'] = 'Constructed BO1'
        
        # Migrate rank format_type fields
        for rank_key in ['constructed_rank', 'limited_rank']:
            if rank_key in data and 'format_type' in data[rank_key]:
                if data[rank_key]['format_type'] == 'Constructed':
                    data[rank_key]['format_type'] = 'Constructed BO1'

# === TEXTUAL WIDGETS ===

class EditableText(Static):
    """Custom inline editable text widget."""
    
    def __init__(self, initial_value: str = "", **kwargs):
        super().__init__(**kwargs)
        self.initial_value = initial_value
        self.is_editing = False
    
    def compose(self) -> ComposeResult:
        yield Label(self.initial_value, classes="editable-display")
        yield Input(value=self.initial_value, classes="editable-input hidden")
    
    def on_mount(self) -> None:
        self._label = self.query_one(".editable-display", Label)
        self._input = self.query_one(".editable-input", Input)
    
    def on_click(self) -> None:
        """Handle click to enter edit mode."""
        if not self.is_editing:
            self.enter_edit_mode()
    
    def enter_edit_mode(self):
        """Switch to editing mode."""
        self.is_editing = True
        self._input.value = str(self._label.renderable)
        self._label.add_class("hidden")
        self._input.remove_class("hidden")
        self._input.focus()
    
    def exit_edit_mode(self):
        """Switch back to display mode."""
        self.is_editing = False
        self._label.update(self._input.value)
        self._input.add_class("hidden")
        self._label.remove_class("hidden")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input == self._input and self.is_editing:
            self.exit_edit_mode()
    
    def on_key(self, event) -> None:
        if event.key == "escape" and self.is_editing:
            self._input.value = str(self._label.renderable)  # Reset
            self.exit_edit_mode()
    
    @property
    def value(self) -> str:
        """Get current value."""
        return self._input.value if self.is_editing else str(self._label.renderable)

class TopPanel(Static):
    """Top panel with season info, current status, and session overview."""
    
    def __init__(self, app_data: AppData):
        super().__init__()
        self.app_data = app_data
    
    def compose(self) -> ComposeResult:
        with Horizontal(classes="top-panel-layout"):
            # Column 1 - Season countdown
            yield Static("🕐 Season: Loading...", classes="top-season")
            
            # Column 2 - Format
            yield Static("📊 BO1", classes="top-format")
            
            # Column 3 - Bars remaining
            yield Static("🎯 BARS: --", classes="top-bars")
            
            # Column 4 - Current rank
            yield Static("📍 Loading...", classes="top-rank")
    
    def on_mount(self) -> None:
        """Update display when mounted."""
        self.update_display()
    
    def update_display(self):
        """Update top panel display."""
        current_rank = self.app_data.get_current_rank()
        format_name = self.app_data.current_format.value.upper()
        stats = self.app_data.stats
        
        # Column 1 - Season countdown with end date
        season_text = "--"
        season_date = ""
        if stats.season_end_date:
            time_left = stats.season_end_date - datetime.now()
            if time_left.total_seconds() > 0:
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                seconds = time_left.seconds % 60
                if days > 0:
                    season_text = f"{days:02d}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
                else:
                    season_text = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
                # Format the end date 
                season_date = f"[{stats.season_end_date.strftime('%b %d %I:%M%p')}]"
            else:
                season_text = "ENDED"
        
        season_content = f"🕐 Season: {season_text} {season_date}"
        
        # Column 2 - Format
        format_content = f"📊 {format_name}"
        
        # Column 3 - Bars remaining or Mythic trophy
        if current_rank.is_mythic():
            bars_content = f"🏆 [rgb(255,140,0)]MYTHIC[/rgb(255,140,0)]"
        else:
            bars_remaining = current_rank.get_total_bars_remaining_to_mythic()
            bars_content = f"🎯 BARS: {bars_remaining}"
        
        # Column 4 - Current rank
        tier_name = current_rank.tier.value if hasattr(current_rank.tier, 'value') else current_rank.tier
        rank_text = f"{tier_name} {current_rank.division or 1} ({current_rank.pips}/{current_rank.max_pips})"
        if current_rank.is_mythic():
            if current_rank.mythic_rank:
                rank_text = f"[rgb(255,140,0)]Mythic[/rgb(255,140,0)] #{current_rank.mythic_rank}"
            else:
                rank_text = f"[rgb(255,140,0)]Mythic[/rgb(255,140,0)] {current_rank.mythic_percentage:.1f}%" if current_rank.mythic_percentage else "[rgb(255,140,0)]Mythic[/rgb(255,140,0)]"
        
        rank_content = f"📍 {rank_text}"
        
        # Update the four columns
        try:
            season_widget = self.query_one(".top-season", Static)
            season_widget.update(season_content)
            
            format_widget = self.query_one(".top-format", Static)
            format_widget.update(format_content)
            
            bars_widget = self.query_one(".top-bars", Static)
            bars_widget.update(bars_content)
            
            rank_widget = self.query_one(".top-rank", Static)
            rank_widget.update(rank_content)
        except:
            pass  # Ignore if widgets not found during startup

class RankProgressPanel(Static):
    """Left panel showing interactive rank progression."""
    
    def __init__(self, app_data: AppData):
        super().__init__()
        self.app_data = app_data
    
    def compose(self) -> ComposeResult:
        current_rank = self.app_data.get_current_rank()
        format_name = self.app_data.current_format.value
        
        with Vertical():
            yield Static(f"─ [{format_name.upper()}] Rank Progress ─", classes="panel-header")
            
            # Show mythic display if mythic is achieved and enabled
            if current_rank.tier == RankTier.MYTHIC and self.app_data.show_mythic_progress:
                yield Static("")  # Empty line for spacing
                yield self._create_mythic_display(current_rank)
                yield Static("─" * 30, classes="separator")
            else:
                yield Static("─" * 30, classes="separator")
            
            # Always show rank bars
            yield self._create_rank_bars()
            
            yield Static("─" * 30, classes="separator")
    
    def _create_mythic_display(self, rank: ManualRank) -> Static:
        """Create Mythic achievement display."""
        if rank.mythic_rank:
            current_text = f"Current: #{rank.mythic_rank}"
        else:
            current_text = f"Current: {rank.mythic_percentage:.1f}%" if rank.mythic_percentage else "Current: --"
        
        return Static(f"""🏆 [rgb(255,140,0)]MYTHIC ACHIEVED![/rgb(255,140,0)] 🏆

{current_text}""", classes="mythic-display")
    
    def _create_rank_bars(self) -> Static:
        """Create rank progression bars as a single text widget."""
        current_rank = self.app_data.get_current_rank()
        
        # Build text display
        lines = []
        
        # Boss fight indicator
        if current_rank.is_boss_fight():
            next_tier = current_rank.next_tier()
            lines.append(f"🔥 [bold red]BOSS FIGHT![/bold red] Next win → [bold]{next_tier}[/bold]! 🔥")
            lines.append("")  # Empty line for spacing
        
        # All rank tiers from Mythic down to Bronze
        tier_order = list(RankTier)
        tier_order.reverse()  # Mythic at top
        
        for tier in tier_order:
            # Skip hidden tiers entirely
            if tier in self.app_data.hidden_tiers:
                continue
                
            if tier == RankTier.MYTHIC:
                # Show mythic with just percentage/rank, no bars
                if current_rank.tier == RankTier.MYTHIC:
                    if current_rank.mythic_rank:
                        mythic_display = f"#{current_rank.mythic_rank}"
                    else:
                        mythic_display = f"{current_rank.mythic_percentage:.1f}%" if current_rank.mythic_percentage else "0%"
                    
                    # Highlight mythic if it's current rank
                    tier_color = self._get_tier_color(RankTier.MYTHIC)
                    mythic_text = f"[black on {tier_color}]Mythic   [/black on {tier_color}]"
                    lines.append(f"{mythic_text} {mythic_display}")
                else:
                    lines.append("Mythic    --")
            else:
                # Check if this tier should be collapsed
                if tier in self.app_data.collapsed_tiers:
                    tier_color = self._get_tier_color(tier)
                    lines.append(f"{tier.value:<9}   [{tier_color}][██████████████████████][/{tier_color}]")
                else:
                    # Show all 4 divisions for this tier
                    for div in range(1, 5):
                        bars = self._create_bar_display(tier, div, current_rank)
                        # Only show goal marker if goal not yet achieved
                        goal_marker = ""
                        if self._is_goal_rank(tier, div):
                            current_rank = self.app_data.get_current_rank()
                            stats = self.app_data.stats
                            goal_attained = self._is_goal_attained(current_rank, stats.session_goal_tier, stats.session_goal_division)
                            if not goal_attained:
                                goal_marker = " ←GOAL"
                        
                        # Highlight current position with tier-colored background
                        if tier == current_rank.tier and div == current_rank.division:
                            tier_color = self._get_tier_color(tier)
                            tier_text = f"[black on {tier_color}]{tier.value:<9}[/black on {tier_color}]"
                            div_text = f"[black on {tier_color}]{div}[/black on {tier_color}]"
                            
                            # Add boss fight indicator to current tier line
                            boss_marker = " ⚔️ [bold red]BOSS TIER![/bold red]" if current_rank.is_boss_fight() else ""
                        else:
                            tier_text = f"{tier.value:<9}"
                            div_text = f"{div}"
                            boss_marker = ""
                        
                        lines.append(f"{tier_text} {div_text} {bars}{goal_marker}{boss_marker}")
        
        return Static("\n".join(lines), classes="rank-bars")
    
    def _create_bar_display(self, tier: RankTier, division: int, current_rank: ManualRank) -> str:
        """Create bar display for a specific tier/division."""
        # Use the app's current format to determine bar count
        max_pips = 6 if self.app_data.current_format in [FormatType.CONSTRUCTED_BO1, FormatType.CONSTRUCTED_BO3] else 4
        bars = []
        
        # Determine if this position is filled based on current rank
        is_filled = self._is_position_filled(tier, division, current_rank)
        
        if is_filled:
            # All bars filled - use tier-specific colors
            tier_color = self._get_tier_color(tier)
            for _ in range(max_pips):
                bars.append(f"[{tier_color}][██][/{tier_color}]")
        else:
            # Check if this is current position (partially filled)
            if tier == current_rank.tier and division == current_rank.division:
                # Use tier-specific color for current position bars too
                tier_color = self._get_tier_color(tier)
                for i in range(max_pips):
                    if i < current_rank.pips:
                        bars.append(f"[{tier_color}][██][/{tier_color}]")
                    else:
                        bars.append("[  ]")
            else:
                # Empty bars
                for _ in range(max_pips):
                    bars.append("[  ]")
        
        return "".join(bars)
    
    def _get_tier_color(self, tier: RankTier) -> str:
        """Get the color for a specific tier."""
        tier_colors = {
            RankTier.BRONZE: "rgb(139,69,19)",    # Bronze
            RankTier.SILVER: "rgb(192,192,192)",  # Silver
            RankTier.GOLD: "rgb(255,215,0)",      # Gold
            RankTier.PLATINUM: "rgb(0,206,209)",  # Cyan/Teal
            RankTier.DIAMOND: "rgb(138,43,226)",  # Royal purple
            RankTier.MYTHIC: "rgb(255,140,0)"     # True planeswalker orange
        }
        return tier_colors.get(tier, "white")
    
    def _is_position_filled(self, tier: RankTier, division: int, current_rank: ManualRank) -> bool:
        """Check if a rank position should be displayed as filled."""
        # Don't try to fill mythic bars - mythic doesn't have bars
        if tier == RankTier.MYTHIC:
            return False
            
        # If current rank is mythic, all non-mythic positions are filled
        if current_rank.is_mythic():
            return True
        
        tier_order = list(RankTier)[:-1]  # Exclude Mythic
        current_tier_idx = tier_order.index(current_rank.tier)
        check_tier_idx = tier_order.index(tier)
        
        # Lower tiers are filled
        if check_tier_idx < current_tier_idx:
            return True
        
        # Same tier, lower divisions are filled
        if check_tier_idx == current_tier_idx and division > current_rank.division:
            return True
        
        return False
    
    def _is_goal_rank(self, tier: RankTier, division: int) -> bool:
        """Check if this is the session goal rank."""
        stats = self.app_data.stats
        return (stats.session_goal_tier == tier and 
                stats.session_goal_division == division)
    
    def _is_goal_attained(self, current_rank: ManualRank, goal_tier, goal_division) -> bool:
        """Check if the session goal has been attained."""
        if not goal_tier:
            return False
            
        # Handle mythic goal
        if goal_tier == RankTier.MYTHIC or str(goal_tier) == "Mythic":
            return current_rank.is_mythic()
            
        # Compare tier and division
        current_tier_str = current_rank.tier.value if hasattr(current_rank.tier, 'value') else str(current_rank.tier)
        goal_tier_str = goal_tier.value if hasattr(goal_tier, 'value') else str(goal_tier)
        
        tier_order = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Mythic"]
        
        try:
            current_tier_idx = tier_order.index(current_tier_str)
            goal_tier_idx = tier_order.index(goal_tier_str)
            
            # Higher tier achieved
            if current_tier_idx > goal_tier_idx:
                return True
                
            # Same tier, check division (lower division number = higher rank)
            if current_tier_idx == goal_tier_idx:
                return current_rank.division <= goal_division
                
        except ValueError:
            pass
            
        return False

class StatsPanel(Static):
    """Right panel showing session and season statistics."""
    
    def __init__(self, app_data: AppData):
        super().__init__()
        self.app_data = app_data
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("─ Session & Season Stats ─", classes="panel-header")
            
            # Session goal
            yield self._create_goal_section()
            yield Static("─" * 30, classes="separator")
            
            # Current session
            yield self._create_session_section()
            yield Static("─" * 30, classes="separator")
            
            # Season totals
            yield self._create_season_section()
            yield Static("─" * 30, classes="separator")
            
            # Session history
            yield self._create_history_section()
            yield Static("─" * 30, classes="separator")
    
    def _create_goal_section(self) -> Static:
        """Create session goal section."""
        stats = self.app_data.stats
        if stats.session_goal_tier:
            tier_name = stats.session_goal_tier.value if hasattr(stats.session_goal_tier, 'value') else stats.session_goal_tier
            
            # Handle mythic goal (no division) 
            if stats.session_goal_tier == RankTier.MYTHIC or str(stats.session_goal_tier) == "Mythic":
                goal_text = "Mythic"
            else:
                goal_text = f"{tier_name} {stats.session_goal_division or 4}"
            
            # Check if goal is attained
            current_rank = self.app_data.get_current_rank()
            goal_attained = self._is_goal_attained(current_rank, stats.session_goal_tier, stats.session_goal_division)
            
            if goal_attained:
                return Static(f"🎯 SESSION GOAL: [{goal_text}] ✅ ACHIEVED!", classes="goal-section")
            else:
                return Static(f"🎯 SESSION GOAL: [{goal_text}] [G] Change", classes="goal-section")
        else:
            return Static("🎯 SESSION GOAL: [None]", classes="goal-section")
    
    def _is_goal_attained(self, current_rank: ManualRank, goal_tier, goal_division) -> bool:
        """Check if the session goal has been attained."""
        if not goal_tier:
            return False
            
        # Handle mythic goal
        if goal_tier == RankTier.MYTHIC or str(goal_tier) == "Mythic":
            return current_rank.is_mythic()
            
        # Compare tier and division
        current_tier_str = current_rank.tier.value if hasattr(current_rank.tier, 'value') else str(current_rank.tier)
        goal_tier_str = goal_tier.value if hasattr(goal_tier, 'value') else str(goal_tier)
        
        tier_order = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Mythic"]
        
        try:
            current_tier_idx = tier_order.index(current_tier_str)
            goal_tier_idx = tier_order.index(goal_tier_str)
            
            # Higher tier achieved
            if current_tier_idx > goal_tier_idx:
                return True
                
            # Same tier, check division (lower division number = higher rank)
            if current_tier_idx == goal_tier_idx:
                return current_rank.division <= goal_division
                
        except ValueError:
            pass
            
        return False
    
    def _create_session_section(self) -> Static:
        """Create current session stats."""
        stats = self.app_data.stats
        format_name = self.app_data.current_format.value.upper()
        
        # Session timing (active time only, excluding paused time)
        duration_text = "00m 00s"
        pause_status = ""
        if stats.session_start_time:
            try:
                duration = stats.get_active_session_duration()
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                if hours > 0:
                    duration_text = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
                elif minutes > 0:
                    duration_text = f"{minutes:02d}m {seconds:02d}s"
                else:
                    duration_text = f"00m {seconds:02d}s"
                
                # Add pause indicator
                if stats.session_paused:
                    pause_status = " ⏸️ PAUSED"
                
            except:
                duration_text = "00m 00s"
        
        # Format start time safely
        start_time = "Not set"
        if stats.session_start_time:
            try:
                if isinstance(stats.session_start_time, str):
                    session_start = datetime.fromisoformat(stats.session_start_time)
                else:
                    session_start = stats.session_start_time
                start_time = session_start.strftime("%I:%M %p")
            except:
                start_time = "Invalid time"
        
        # Streak info
        if stats.current_win_streak > 0:
            streak_text = f"W{stats.current_win_streak}"
        elif stats.current_loss_streak > 0:
            streak_text = f"L{stats.current_loss_streak}"
        else:
            streak_text = "None"
        
        current_streak_text = f"{stats.current_win_streak} / L{stats.current_loss_streak}"
        
        # Time since last result - show both real and active time
        last_result_text = "No games yet"
        if stats.last_result_time:
            try:
                real_seconds, active_seconds = stats.get_time_since_last_result()
                
                # Format real time
                real_minutes = real_seconds // 60
                real_secs = real_seconds % 60
                real_text = f"{real_minutes:02d}m {real_secs:02d}s"
                
                # Format active time 
                active_minutes = active_seconds // 60
                active_secs = active_seconds % 60
                active_text = f"{active_minutes:02d}m {active_secs:02d}s"
                
                # Show both if different, otherwise just one
                if real_seconds != active_seconds:
                    last_result_text = f"{real_text} ago ({active_text} active)"
                else:
                    last_result_text = f"{real_text} ago"
                    
            except:
                last_result_text = "Invalid time"
        
        # Game timer info
        game_timer_text = ""
        avg_game_text = ""
        if stats.game_start_time:
            game_seconds = int(stats.get_current_game_duration())
            game_minutes = game_seconds // 60
            game_secs = game_seconds % 60
            game_timer_text = f"  Current: {game_minutes:02d}m {game_secs:02d}s ⏰"
        
        if stats.game_durations:
            avg_seconds = int(stats.get_average_game_duration())
            avg_minutes = avg_seconds // 60
            avg_secs = avg_seconds % 60
            avg_game_text = f"Avg Game: [{avg_minutes:02d}m {avg_secs:02d}s]  "
        
        return Static(f"""📊 CURRENT SESSION [{format_name}]
Started:  [{start_time}]  Duration: {duration_text}{pause_status}
Record:   [{stats.session_wins}W] - [{stats.session_losses}L]  {stats.get_session_win_rate():.1f}%
Streaks:  W{current_streak_text} (current)
{avg_game_text}Last: {last_result_text}{game_timer_text}""", classes="session-section", id="session-section")
    
    def _create_season_section(self) -> Static:
        """Create season total stats."""
        stats = self.app_data.stats
        format_name = self.app_data.current_format.value.upper()
        
        start_rank = "Not set"
        if stats.season_start_rank:
            # Handle both string and rank object formats
            if hasattr(stats.season_start_rank, 'tier'):
                # It's a rank object - don't show pips for season start
                tier_name = stats.season_start_rank.tier.value if hasattr(stats.season_start_rank.tier, 'value') else stats.season_start_rank.tier
                start_rank = f"{tier_name} {stats.season_start_rank.division}"
            else:
                # It's just a string
                start_rank = str(stats.season_start_rank)
        
        return Static(f"""🏆 SEASON TOTAL [{format_name}]
Record:   [{stats.season_wins}W] - [{stats.season_losses}L]  {stats.get_season_win_rate():.1f}%
Best:     [W{stats.best_win_streak}]  Worst: [L{stats.worst_loss_streak}]
Started:  [{start_rank}]""", classes="season-section")
    
    def _create_history_section(self) -> Static:
        """Create session history section."""
        stats = self.app_data.stats
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Show last 5 completed sessions
        history_lines = ["📈 SESSION HISTORY"]
        
        if stats.session_history:
            for i, session in enumerate(reversed(stats.session_history[-5:])):
                # Format date display
                if session.date == today:
                    date_display = "Today"
                else:
                    try:
                        session_date = datetime.strptime(session.date, "%Y-%m-%d")
                        date_display = session_date.strftime("%m/%d")
                    except:
                        date_display = session.date[-5:]  # Last 5 chars (MM-DD)
                
                # Calculate win rate
                total_games = session.wins + session.losses
                win_rate = (session.wins / total_games * 100) if total_games > 0 else 0
                
                # Format bar progress
                bar_text = f"{session.bar_progress:+d} bars" if session.bar_progress != 0 else "±0 bars"
                
                history_lines.append(f"{date_display:<9} {session.wins}W-{session.losses}L ({win_rate:.1f}%) {bar_text}")
        else:
            history_lines.append("No completed sessions yet")
        
        # Add current session if active
        if stats.session_wins > 0 or stats.session_losses > 0:
            current_rank = self.app_data.get_current_rank()
            session_bars = self._calculate_session_bar_progress(stats, current_rank)
            bar_text = f"{session_bars:+d} bars" if session_bars != 0 else "±0 bars"
            
            history_lines.append("─" * 35)
            history_lines.append(f"Current:  {stats.session_wins}W-{stats.session_losses}L ({stats.get_session_win_rate():.1f}%) {bar_text}")
        
        # Add recent game notes section
        if hasattr(stats, 'game_notes') and stats.game_notes:
            history_lines.append("")
            history_lines.append("📝 RECENT NOTES")
            
            # Show last 3 notes
            recent_notes = stats.game_notes[-3:] if len(stats.game_notes) > 3 else stats.game_notes
            for note in reversed(recent_notes):
                # Handle timestamp safely with smart date/time display
                if 'timestamp' in note and isinstance(note['timestamp'], datetime):
                    now = datetime.now()
                    note_time = note['timestamp']
                    
                    # If note is from today, show just time. Otherwise show date + time
                    if note_time.date() == now.date():
                        time_str = note_time.strftime("%H:%M")
                    else:
                        time_str = note_time.strftime("%m/%d %H:%M")
                else:
                    time_str = "??:??"
                
                # Create summary line
                result_icon = "🏆" if note.get('result') == 'Win' else "💀" if note.get('result') == 'Loss' else "❓"
                summary = f"[{time_str}] {result_icon} {note['play_draw']}"
                if note['opponent_deck']:
                    summary += f" vs {note['opponent_deck'][:12]}"  # Truncate long names
                
                history_lines.append(summary)
                
                # Add notes preview if available
                if note['notes']:
                    preview = note['notes'][:30] + "..." if len(note['notes']) > 30 else note['notes']
                    history_lines.append(f"  {preview}")
        
        return Static("\n".join(history_lines), classes="history-section")
    
    def _calculate_session_bar_progress(self, stats: SessionStats, current_rank: ManualRank) -> int:
        """Calculate how many bars gained/lost this session."""
        if not stats.session_start_rank:
            return 0
            
        # Get starting rank for this session
        start_rank = stats.session_start_rank
        if hasattr(start_rank, 'get_total_bars_remaining_to_mythic'):
            start_bars = start_rank.get_total_bars_remaining_to_mythic()
        else:
            start_bars = 0
            
        current_bars = current_rank.get_total_bars_remaining_to_mythic()
        
        # Progress = reduction in bars remaining (higher rank = fewer bars remaining)
        return start_bars - current_bars

class EditStatsModal(ModalScreen):
    """Modal dialog for editing session/season stats."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    CSS = """
    EditStatsModal {
        align: center middle;
    }
    
    #stats-dialog {
        width: 90;
        height: 32;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }
    
    .stats-columns {
        height: 1fr;
    }
    
    .stats-column {
        width: 50%;
        padding: 0 1;
    }
    
    .stats-row {
        height: 3;
        margin: 0 0 1 0;
    }
    
    .stats-label {
        width: 16;
        content-align: right middle;
    }
    
    .stats-input {
        width: 1fr;
        margin-left: 1;
    }
    
    .modal-buttons {
        height: 4;
        margin-top: 2;
        content-align: center middle;
    }
    
    .modal-title {
        height: 3;
        text-style: bold;
        background: $primary;
        color: $text;
        content-align: center middle;
        margin-bottom: 1;
    }
    
    .column-header {
        text-style: bold;
        background: $primary;
        color: $text;
        margin-bottom: 1;
        content-align: center middle;
    }
    """
    
    def __init__(self, stats: 'SessionStats', **kwargs):
        super().__init__(**kwargs)
        self.stats = stats
        self.result = None
    
    def compose(self) -> ComposeResult:
        with Container(id="stats-dialog"):
            yield Label("Edit Session & Season Stats", classes="modal-title")
            
            # Two-column layout
            with Horizontal(classes="stats-columns"):
                # Left Column - Session Stats
                with Vertical(classes="stats-column"):
                    yield Label("📊 SESSION STATS", classes="column-header")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Session Start:", classes="stats-label")
                        start_time_str = self.stats.session_start_time.strftime("%H:%M") if self.stats.session_start_time else "14:00"
                        yield Input(value=start_time_str, id="session-start-input", placeholder="HH:MM", classes="stats-input")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Session Wins:", classes="stats-label")
                        yield Input(value=str(self.stats.session_wins), id="session-wins-input", placeholder="0", classes="stats-input")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Session Losses:", classes="stats-label")
                        yield Input(value=str(self.stats.session_losses), id="session-losses-input", placeholder="0", classes="stats-input")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Current Win Streak:", classes="stats-label")
                        yield Input(value=str(self.stats.current_win_streak), id="current-win-input", placeholder="0", classes="stats-input")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Current Loss Streak:", classes="stats-label")
                        yield Input(value=str(self.stats.current_loss_streak), id="current-loss-input", placeholder="0", classes="stats-input")
                
                # Right Column - Season Stats
                with Vertical(classes="stats-column"):
                    yield Label("🏆 SEASON STATS", classes="column-header")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Season Wins:", classes="stats-label")
                        yield Input(value=str(self.stats.season_wins), id="season-wins-input", placeholder="0", classes="stats-input")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Season Losses:", classes="stats-label")
                        yield Input(value=str(self.stats.season_losses), id="season-losses-input", placeholder="0", classes="stats-input")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Best Win Streak:", classes="stats-label")
                        yield Input(value=str(self.stats.best_win_streak), id="best-win-input", placeholder="0", classes="stats-input")
                    
                    with Horizontal(classes="stats-row"):
                        yield Label("Worst Loss Streak:", classes="stats-label")
                        yield Input(value=str(self.stats.worst_loss_streak), id="worst-loss-input", placeholder="0", classes="stats-input")
            
            with Horizontal(classes="modal-buttons"):
                yield Button("Save", id="save-btn", variant="success")
                yield Button("Cancel", id="cancel-btn", variant="default")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_changes()
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()
    
    def _save_changes(self):
        """Save the edited values."""
        try:
            # Session start time
            session_start_str = self.query_one("#session-start-input", Input).value
            if session_start_str:
                hour, minute = map(int, session_start_str.split(":"))
                if self.stats.session_start_time:
                    new_start = self.stats.session_start_time.replace(hour=hour, minute=minute)
                else:
                    new_start = datetime.now().replace(hour=hour, minute=minute)
                self.stats.session_start_time = new_start
            
            # Session wins/losses
            session_wins_str = self.query_one("#session-wins-input", Input).value.strip()
            if session_wins_str.isdigit():
                self.stats.session_wins = int(session_wins_str)
            elif session_wins_str == "":
                self.stats.session_wins = 0
                
            session_losses_str = self.query_one("#session-losses-input", Input).value.strip()
            if session_losses_str.isdigit():
                self.stats.session_losses = int(session_losses_str)
            elif session_losses_str == "":
                self.stats.session_losses = 0
            
            # Current streaks
            current_win_str = self.query_one("#current-win-input", Input).value.strip()
            if current_win_str.isdigit():
                self.stats.current_win_streak = int(current_win_str)
            elif current_win_str == "":
                self.stats.current_win_streak = 0
                
            current_loss_str = self.query_one("#current-loss-input", Input).value.strip()
            if current_loss_str.isdigit():
                self.stats.current_loss_streak = int(current_loss_str)
            elif current_loss_str == "":
                self.stats.current_loss_streak = 0
            
            # Season wins/losses
            season_wins_str = self.query_one("#season-wins-input", Input).value.strip()
            if season_wins_str.isdigit():
                self.stats.season_wins = int(season_wins_str)
            elif season_wins_str == "":
                self.stats.season_wins = 0
                
            season_losses_str = self.query_one("#season-losses-input", Input).value.strip()
            if season_losses_str.isdigit():
                self.stats.season_losses = int(season_losses_str)
            elif season_losses_str == "":
                self.stats.season_losses = 0
            
            # Best win streak
            best_win_str = self.query_one("#best-win-input", Input).value.strip()
            if best_win_str.isdigit():
                self.stats.best_win_streak = int(best_win_str)
            elif best_win_str == "":
                self.stats.best_win_streak = 0
            
            # Worst loss streak
            worst_loss_str = self.query_one("#worst-loss-input", Input).value.strip()
            if worst_loss_str.isdigit():
                self.stats.worst_loss_streak = int(worst_loss_str)
            elif worst_loss_str == "":
                self.stats.worst_loss_streak = 0
            
                
            self.result = "saved"
            self.app.pop_screen()
            
        except Exception as e:
            self.app.notify(f"Error saving stats: {e}", severity="error")
    
    def action_cancel(self) -> None:
        self.app.pop_screen()

class SetGoalModal(ModalScreen):
    """Modal dialog for setting session goal with dropdowns."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, current_rank: ManualRank, format_type: FormatType, stats: 'SessionStats', **kwargs):
        super().__init__(**kwargs)
        self.current_rank = current_rank
        self.format_type = format_type
        self.stats = stats
        self.result = None
    
    def compose(self) -> ComposeResult:
        with Container(classes="goal-modal-container"):
            yield Static("Set Session Goal", classes="modal-title")
            yield Static(f"Current Rank: {self.current_rank}", classes="modal-subtitle")
            
            with Vertical(classes="modal-form"):
                # Tier dropdown
                tier_options = [(tier.value, tier.value) for tier in RankTier]
                if self.stats.session_goal_tier:
                    current_goal_tier = self.stats.session_goal_tier.value if hasattr(self.stats.session_goal_tier, 'value') else str(self.stats.session_goal_tier)
                else:
                    current_goal_tier = "Mythic"
                yield Static("Goal Tier:")
                yield Select(tier_options, value=current_goal_tier, id="goal-tier-select")
                
                # Division dropdown (1-4) - always create, hide for Mythic
                division_label = Static("Goal Division:", id="goal-division-label")
                if current_goal_tier == "Mythic":
                    division_label.display = False
                yield division_label
                
                division_options = [(str(i), str(i)) for i in range(4, 0, -1)]  # 4,3,2,1
                current_goal_div = str(self.stats.session_goal_division) if self.stats.session_goal_division else "4"
                division_select = Select(division_options, value=current_goal_div, id="goal-division-select")
                if current_goal_tier == "Mythic":
                    division_select.display = False
                yield division_select
            
            with Horizontal(classes="modal-buttons"):
                yield Button("Set Goal", id="set-goal", variant="success")
                yield Button("Clear Goal", id="clear-goal", variant="warning")
                yield Button("Cancel", id="cancel", variant="error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "set-goal":
            # Get tier value
            tier_select = self.query_one("#goal-tier-select", Select)
            tier = RankTier(tier_select.value)
            
            if tier == RankTier.MYTHIC:
                self.dismiss((tier, None))
            else:
                # Get division value
                division_select = self.query_one("#goal-division-select", Select)
                division = int(division_select.value)
                self.dismiss((tier, division))
        elif event.button.id == "clear-goal":
            self.dismiss((None, None))
        else:
            self.action_cancel()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle tier selection changes to show/hide division controls."""
        if event.select.id == "goal-tier-select":
            is_mythic = event.value == "Mythic"
            
            # Show/hide division controls
            self.query_one("#goal-division-label").display = not is_mythic
            self.query_one("#goal-division-select").display = not is_mythic
    
    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)

class SetRankModal(ModalScreen):
    """Modal dialog for setting rank with dropdowns."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, current_rank: ManualRank, format_type: FormatType, modal_title: str = "Set Rank", **kwargs):
        super().__init__(**kwargs)
        self.current_rank = current_rank
        self.format_type = format_type
        self.modal_title = modal_title
        self.result = None
    
    def compose(self) -> ComposeResult:
        with Container(classes="rank-modal-container"):
            yield Static(self.modal_title, classes="modal-title")
            yield Static(f"Current: {self.current_rank}", classes="modal-subtitle")
            
            with Vertical(classes="modal-form"):
                # Tier dropdown
                tier_options = [(tier.value, tier.value) for tier in RankTier]
                current_tier = self.current_rank.tier.value if hasattr(self.current_rank.tier, 'value') else self.current_rank.tier
                yield Static("Tier:")
                yield Select(tier_options, value=current_tier, id="tier-select")
                
                # Division dropdown (1-4) - always create, hide for Mythic
                division_label = Static("Division:", id="division-label")
                if current_tier == "Mythic":
                    division_label.display = False
                yield division_label
                
                division_options = [(str(i), str(i)) for i in range(4, 0, -1)]
                current_div = str(self.current_rank.division) if self.current_rank.division else "1"
                division_select = Select(division_options, value=current_div, id="division-select")
                if current_tier == "Mythic":
                    division_select.display = False
                yield division_select
                
                # Pips dropdown - always create, hide for Mythic
                pips_label = Static("Pips:", id="pips-label")
                if current_tier == "Mythic":
                    pips_label.display = False
                yield pips_label
                
                max_pips = 6 if self.format_type in [FormatType.CONSTRUCTED_BO1, FormatType.CONSTRUCTED_BO3] else 4
                pip_options = [(str(i), str(i)) for i in range(max_pips)]
                pips_select = Select(pip_options, value=str(self.current_rank.pips), id="pips-select")
                if current_tier == "Mythic":
                    pips_select.display = False
                yield pips_select
                
                # Mythic options - always create, hide for non-Mythic
                mythic_type_label = Static("Mythic Type:", id="mythic-type-label")
                if current_tier != "Mythic":
                    mythic_type_label.display = False
                yield mythic_type_label
                
                mythic_type_options = [("Percentage", "Percentage"), ("Rank Number", "Rank Number")]
                current_type = "Rank Number" if self.current_rank.mythic_rank else "Percentage"
                mythic_type_select = Select(mythic_type_options, value=current_type, id="mythic-type")
                if current_tier != "Mythic":
                    mythic_type_select.display = False
                yield mythic_type_select
                
                mythic_value_label = Static("Mythic Value:", id="mythic-value-label")
                if current_tier != "Mythic":
                    mythic_value_label.display = False
                yield mythic_value_label
                
                if self.current_rank.mythic_rank:
                    current_value = str(self.current_rank.mythic_rank)
                    placeholder = "1247"
                else:
                    current_value = str(self.current_rank.mythic_percentage) if self.current_rank.mythic_percentage else "95.0"
                    placeholder = "95.0"
                mythic_value_input = Input(value=current_value, placeholder=placeholder, id="mythic-value")
                if current_tier != "Mythic":
                    mythic_value_input.display = False
                yield mythic_value_input
            
            with Horizontal(classes="modal-buttons"):
                yield Button("Set Rank", id="set-rank", variant="success")
                yield Button("Cancel", id="cancel", variant="error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "set-rank":
            # Get tier value
            tier_select = self.query_one("#tier-select", Select)
            try:
                tier = RankTier(tier_select.value) if tier_select.value != Select.BLANK else RankTier.BRONZE
            except (ValueError, TypeError):
                tier = RankTier.BRONZE  # Default to Bronze
            
            if tier == RankTier.MYTHIC:
                # Handle Mythic rank - check if percentage or rank number
                mythic_type_select = self.query_one("#mythic-type", Select)
                mythic_value_input = self.query_one("#mythic-value", Input)
                
                mythic_type = mythic_type_select.value if mythic_type_select.value != Select.BLANK else "Percentage"
                if mythic_type == "Rank Number":
                    # Mythic rank number (e.g., #1247) - must be >= 1
                    try:
                        mythic_rank = int(mythic_value_input.value) if mythic_value_input.value else 1247
                        mythic_rank = max(1, mythic_rank)  # Ensure rank >= 1
                    except:
                        mythic_rank = 1247
                    
                    new_rank = ManualRank(
                        tier=tier,
                        division=None,
                        pips=0,
                        mythic_rank=mythic_rank,
                        format_type=self.format_type
                    )
                else:
                    # Mythic percentage (e.g., 95.7%) - must be 0-100
                    try:
                        mythic_percentage = float(mythic_value_input.value) if mythic_value_input.value else 95.0
                        mythic_percentage = max(0.0, min(100.0, mythic_percentage))  # Clamp to 0-100
                    except:
                        mythic_percentage = 95.0
                    
                    new_rank = ManualRank(
                        tier=tier,
                        division=None,
                        pips=0,
                        mythic_percentage=mythic_percentage,
                        format_type=self.format_type
                    )
            else:
                # Handle regular ranks
                division_select = self.query_one("#division-select", Select) 
                pips_select = self.query_one("#pips-select", Select)
                
                # Handle NoSelection cases with defaults
                try:
                    division = int(division_select.value) if division_select.value != Select.BLANK else 4
                except (ValueError, TypeError):
                    division = 4  # Default to division 4
                
                try:
                    pips = int(pips_select.value) if pips_select.value != Select.BLANK else 0
                except (ValueError, TypeError):
                    pips = 0  # Default to 0 pips
                
                new_rank = ManualRank(
                    tier=tier,
                    division=division,
                    pips=pips,
                    format_type=self.format_type
                )
            
            self.result = new_rank
            self.dismiss(new_rank)
        else:
            self.action_cancel()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle tier selection changes to show/hide appropriate widgets."""
        if event.select.id == "tier-select":
            is_mythic = event.value == "Mythic"
            
            # Show/hide division and pips controls
            self.query_one("#division-label").display = not is_mythic
            self.query_one("#division-select").display = not is_mythic
            self.query_one("#pips-label").display = not is_mythic
            self.query_one("#pips-select").display = not is_mythic
            
            # Show/hide mythic controls
            self.query_one("#mythic-type-label").display = is_mythic
            self.query_one("#mythic-type").display = is_mythic
            self.query_one("#mythic-value-label").display = is_mythic
            self.query_one("#mythic-value").display = is_mythic
            
        elif event.select.id == "mythic-type":
            # Handle mythic type changes - reset to appropriate default
            mythic_value_input = self.query_one("#mythic-value", Input)
            
            if event.value == "Rank Number":
                # Switch to rank number - clear field and set placeholder
                mythic_value_input.value = ""
                mythic_value_input.placeholder = "1247"
            else:
                # Switch to percentage - clear field and set placeholder  
                mythic_value_input.value = ""
                mythic_value_input.placeholder = "95.0"

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)

class ConfirmationModal(ModalScreen):
    """Modal dialog for confirmations."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.result = False
    
    def compose(self) -> ComposeResult:
        with Container(classes="confirmation-modal-container"):
            yield Static(self.message, classes="confirmation-modal-message")
            with Horizontal(classes="confirmation-modal-buttons"):
                yield Button("Yes", id="confirm-yes", variant="success")
                yield Button("No", id="confirm-no", variant="error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.result = True
        else:
            self.result = False
        self.dismiss(self.result)
    
    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(False)

class NotesManagerModal(ModalScreen):
    """Modal for viewing and editing all game notes."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "edit_selected", "Edit Selected"),
        Binding("delete", "delete_selected", "Delete Selected"),
    ]
    
    CSS = """
    NotesManagerModal {
        align: center middle;
    }
    
    #notes-manager-dialog {
        width: 95;
        height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    
    .notes-list {
        height: 1fr;
        border: solid $secondary;
        margin: 1 0;
    }
    
    .manager-buttons {
        height: 3;
        content-align: center middle;
    }
    """
    
    def __init__(self, notes_list, **kwargs):
        super().__init__(**kwargs)
        self.notes_list = notes_list
        self.selected_note_id = None
    
    def compose(self) -> ComposeResult:
        with Container(id="notes-manager-dialog"):
            yield Label("Game Notes Manager", classes="modal-title")
            yield Label("Use ↑↓ to select, Enter to edit, Delete to remove", classes="help-text")
            
            table = DataTable(id="notes-table", classes="notes-list")
            table.add_columns("Time", "Result", "Play/Draw", "Opponent", "Notes Preview")
            table.cursor_type = "row"
            
            # Populate table
            for note in self.notes_list:
                # Handle timestamp safely with smart date/time display
                if 'timestamp' in note and isinstance(note['timestamp'], datetime):
                    now = datetime.now()
                    note_time = note['timestamp']
                    
                    # If note is from today, show just time. Otherwise show date + time
                    if note_time.date() == now.date():
                        time_str = note_time.strftime("%H:%M")
                    else:
                        time_str = note_time.strftime("%m/%d %H:%M")
                else:
                    time_str = "??:??"
                
                result_icon = "🏆" if note.get('result') == 'Win' else "💀" if note.get('result') == 'Loss' else "❓"
                preview = note['notes'][:25] + "..." if len(note['notes']) > 25 else note['notes']
                
                table.add_row(
                    time_str,
                    f"{result_icon} {note.get('result', 'Unknown')}",
                    note['play_draw'],
                    note['opponent_deck'][:15] if note['opponent_deck'] else "",
                    preview,
                    key=str(note['id'])
                )
            
            yield table
            
            with Horizontal(classes="manager-buttons"):
                yield Button("Edit Selected", id="edit-btn", variant="primary")
                yield Button("Delete Selected", id="delete-btn", variant="error")
                yield Button("Close", id="close-btn", variant="default")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-btn":
            self.action_edit_selected()
        elif event.button.id == "delete-btn":
            self.action_delete_selected()
        elif event.button.id == "close-btn":
            self.action_cancel()
    
    def on_data_table_row_selected(self, event) -> None:
        """Track which note is selected."""
        if event.row_key:
            try:
                self.selected_note_id = int(str(event.row_key))
            except (ValueError, TypeError):
                self.selected_note_id = None
        else:
            self.selected_note_id = None
    
    def action_edit_selected(self) -> None:
        """Edit the selected note."""
        # Try to get the currently highlighted row from the table
        table = self.query_one("#notes-table", DataTable)
        
        if table.cursor_row is not None and table.cursor_row < len(self.notes_list):
            # Use the cursor position to find the note
            note_to_edit = self.notes_list[table.cursor_row]
            self.selected_note_id = note_to_edit['id']
        
        if not self.selected_note_id:
            self.app.notify("No note selected! Use arrow keys to select a row.", severity="warning")
            return
        
        # Find the note to edit
        note_to_edit = None
        for note in self.notes_list:
            if note['id'] == self.selected_note_id:
                note_to_edit = note
                break
        
        if note_to_edit:
            # Create edit modal with pre-filled data
            edit_modal = GameNotesModal(existing_note=note_to_edit)
            
            def handle_edit_result(result):
                if result:
                    # Update the note
                    note_to_edit.update({
                        'result': result['result'],
                        'play_draw': result['play_draw'],
                        'opponent_deck': result['opponent_deck'],
                        'notes': result['notes']
                    })
                    # Refresh the table display
                    self._refresh_table()
                    self.app.notify("Note updated successfully!", severity="success")
            
            self.app.push_screen(edit_modal, handle_edit_result)
    
    def action_delete_selected(self) -> None:
        """Delete the selected note."""
        # Try to get the currently highlighted row from the table
        table = self.query_one("#notes-table", DataTable)
        
        if table.cursor_row is not None and table.cursor_row < len(self.notes_list):
            # Use the cursor position to find the note
            note_to_delete = self.notes_list[table.cursor_row]
            self.selected_note_id = note_to_delete['id']
        
        if not self.selected_note_id:
            self.app.notify("No note selected! Use arrow keys to select a row.", severity="warning")
            return
        
        # Find the note to get details for confirmation
        note_to_delete = None
        for note in self.notes_list:
            if note['id'] == self.selected_note_id:
                note_to_delete = note
                break
        
        if note_to_delete:
            # Create confirmation message
            opponent = note_to_delete.get('opponent_deck', 'Unknown opponent')
            result = note_to_delete.get('result', 'Unknown result')
            confirm_msg = f"Delete this note?\n\n{result} vs {opponent}\n\nThis cannot be undone."
            
            # Show confirmation dialog
            confirm_modal = ConfirmationModal(confirm_msg)
            
            def handle_confirmation(confirmed):
                if confirmed:
                    # Remove the note
                    for i, note in enumerate(self.notes_list):
                        if note['id'] == self.selected_note_id:
                            self.notes_list.pop(i)
                            break
                    
                    # Refresh the table display
                    self._refresh_table()
                    self.app.notify("Note deleted successfully!", severity="success")
            
            self.app.push_screen(confirm_modal, handle_confirmation)
    
    def _refresh_table(self) -> None:
        """Refresh the table display after changes."""
        table = self.query_one("#notes-table", DataTable)
        table.clear()
        
        # Re-populate table with current notes
        for note in self.notes_list:
            # Handle timestamp safely with smart date/time display
            if 'timestamp' in note and isinstance(note['timestamp'], datetime):
                now = datetime.now()
                note_time = note['timestamp']
                
                # If note is from today, show just time. Otherwise show date + time
                if note_time.date() == now.date():
                    time_str = note_time.strftime("%H:%M")
                else:
                    time_str = note_time.strftime("%m/%d %H:%M")
            else:
                time_str = "??:??"
            
            result_icon = "🏆" if note.get('result') == 'Win' else "💀" if note.get('result') == 'Loss' else "❓"
            preview = note['notes'][:25] + "..." if len(note['notes']) > 25 else note['notes']
            
            table.add_row(
                time_str,
                f"{result_icon} {note.get('result', 'Unknown')}",
                note['play_draw'],
                note['opponent_deck'][:15] if note['opponent_deck'] else "",
                preview,
                key=str(note['id'])
            )
    
    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)

class GameNotesModal(ModalScreen):
    """Modal dialog for adding detailed game notes."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    CSS = """
    GameNotesModal {
        align: center middle;
    }
    
    #notes-dialog {
        width: 90;
        height: 35;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }
    
    .notes-row {
        height: 3;
        margin: 0 0 1 0;
    }
    
    .notes-label {
        width: 18;
        content-align: right middle;
    }
    
    .notes-input {
        width: 1fr;
        margin-left: 1;
    }
    
    .notes-textarea {
        height: 10;
        margin: 1 0;
        border: solid $primary;
        background: $surface;
        color: $text;
        padding: 1;
    }
    
    .notes-textarea:focus {
        border: thick $accent;
    }
    
    .modal-buttons {
        height: 4;
        margin-top: 2;
        content-align: center middle;
        dock: bottom;
    }
    """
    
    def __init__(self, existing_note=None, **kwargs):
        super().__init__(**kwargs)
        self.result = None
        self.existing_note = existing_note
        self.is_editing = existing_note is not None
    
    def compose(self) -> ComposeResult:
        with Container(id="notes-dialog"):
            title = "Edit Game Notes" if self.is_editing else "Add Game Notes"
            yield Label(title, classes="modal-title")
            
            # Pre-fill values if editing
            result_value = self.existing_note.get('result', 'Unknown') if self.existing_note else 'Unknown'
            play_draw_value = self.existing_note.get('play_draw', 'Unknown') if self.existing_note else 'Unknown'
            deck_value = self.existing_note.get('opponent_deck', '') if self.existing_note else ''
            notes_value = self.existing_note.get('notes', '') if self.existing_note else ''
            
            with Horizontal(classes="notes-row"):
                yield Label("Result:", classes="notes-label")
                yield Select([
                    ("Unknown", "Unknown"),
                    ("Win", "Win"),
                    ("Loss", "Loss")
                ], value=result_value, id="result-select", classes="notes-input")
            
            with Horizontal(classes="notes-row"):
                yield Label("Play/Draw:", classes="notes-label")
                yield Select([
                    ("Unknown", "Unknown"),
                    ("Play", "Play"),
                    ("Draw", "Draw")
                ], value=play_draw_value, id="play-draw-select", classes="notes-input")
            
            with Horizontal(classes="notes-row"):
                yield Label("Opponent Deck:", classes="notes-label")
                yield Input(value=deck_value, placeholder="e.g. Mono Red, Esper Control", id="opp-deck-input", classes="notes-input")
            
            yield Label("Game Notes:")
            yield TextArea(text=notes_value, id="notes-textarea", classes="notes-textarea")
            
            with Horizontal(classes="modal-buttons"):
                yield Button("Save Note", id="save-btn", variant="success")
                yield Button("Cancel", id="cancel-btn", variant="default")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_note()
        elif event.button.id == "cancel-btn":
            self.action_cancel()
    
    def _save_note(self):
        """Save the note only."""
        note_data = self._get_note_data()
        self.result = note_data
        self.dismiss(note_data)
    
    def _get_note_data(self):
        """Extract note data from the form."""
        result_select = self.query_one("#result-select", Select)
        play_draw_select = self.query_one("#play-draw-select", Select)
        opp_deck_input = self.query_one("#opp-deck-input", Input)
        notes_textarea = self.query_one("#notes-textarea", TextArea)
        
        return {
            "result": result_select.value if result_select.value != Select.BLANK else "Unknown",
            "play_draw": play_draw_select.value if play_draw_select.value != Select.BLANK else "Unknown",
            "opponent_deck": opp_deck_input.value.strip(),
            "notes": notes_textarea.text.strip(),
            "timestamp": datetime.now()
        }
    
    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)

# === MAIN APPLICATION ===

class ManualTUIApp(App):
    """Main TUI application for manual rank tracking."""
    
    TITLE = "MTGA Mythic TUI Session Tracker (Manual)"
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    .top-panel {
        dock: top;
        height: 3;
        border: solid $primary;
        padding: 0 1;
    }
    
    .top-panel-layout {
        height: 100%;
    }
    
    .top-season {
        width: 40%;
        height: 100%;
        padding: 0 1;
        content-align: left middle;
    }
    
    .top-format {
        width: 20%;
        height: 100%;
        content-align: center middle;
    }
    
    .top-bars {
        width: 20%;
        height: 100%;
        content-align: center middle;
    }
    
    .top-rank {
        width: 20%;
        height: 100%;
        content-align: right middle;
        padding: 0 1;
    }
    
    #main-content {
        layout: horizontal;
        height: 1fr;
        overflow-y: auto;
    }
    
    .left-panel, .right-panel {
        width: 50%;
        height: 100%;
        border: solid $primary;
        margin: 1;
        padding: 1;
        overflow-y: auto;
    }
    
    .footer-controls {
        dock: bottom;
        height: 1;
        background: $surface;
        content-align: center middle;
    }
    
    .panel-header {
        text-style: bold;
        text-align: center;
        color: $accent;
    }
    
    .separator {
        color: $primary;
    }
    
    .help-text, .controls {
        color: $text-muted;
        text-align: center;
        margin: 1 0;
    }
    
    .format-hint {
        color: $text-muted;
        text-align: center;
        margin: 0 1;
        text-style: italic;
    }
    
    .mythic-display {
        text-align: center;
        color: $warning;
        text-style: bold;
    }
    
    .rank-row {
        margin: 0 0 0 1;
    }
    
    .bronze-tier { color: #CD7F32; }
    .silver-tier { color: #C0C0C0; }
    .gold-tier { color: #FFD700; }
    .platinum-tier { color: #E5E4E2; }
    .diamond-tier { color: #B9F2FF; }
    .mythic-row { color: #FF4500; }
    
    .collapsed { color: $text-muted; }
    
    .switch-button {
        width: 100%;
        margin: 0 0 1 0;
    }
    
    .goal-section, .session-section, .season-section, .history-section {
        margin: 1 0;
    }
    
    .modal-container {
        width: 50;
        height: 10;
        border: solid $primary;
        background: $surface;
        padding: 2;
    }
    
    .modal-message {
        text-align: center;
        margin: 0 0 2 0;
    }
    
    .modal-buttons {
        align: center middle;
    }
    
    .editable-display:hover {
        background: $accent 30%;
        text-style: underline;
    }
    
    .hidden {
        display: none;
    }
    
    /* Modal Styling */
    ConfirmationModal {
        align: center middle;
    }
    
    SetRankModal {
        align: center middle;
    }
    
    .confirmation-modal-container {
        width: 50;
        height: 12;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }
    
    .rank-modal-container {
        width: 60;
        height: 35;
        border: solid $primary;
        background: $surface;
        padding: 2;
        overflow-y: auto;
    }
    
    SetGoalModal {
        align: center middle;
    }
    
    .goal-modal-container {
        width: 60;
        height: 25;
        border: solid $primary;
        background: $surface;
        padding: 2;
        overflow-y: auto;
    }
    
    .confirmation-modal-message {
        width: 100%;
        text-align: center;
        margin: 1 0;
    }
    
    .confirmation-modal-buttons {
        width: 100%;
        align: center middle;
    }
    """
    
    BINDINGS = [
        Binding("w", "add_win", "Add Win"),
        Binding("l", "add_loss", "Add Loss"),
        Binding("plus", "add_win", "Add Win (+)"),
        Binding("minus", "add_loss", "Add Loss (-)"),
        Binding("f", "switch_format", "Switch Format"),
        Binding("g", "set_goal", "Set Goal"),
        Binding("m", "toggle_mythic", "Toggle Mythic"),
        Binding("c", "collapse_tiers", "Collapse"),
        Binding("h", "hide_tiers", "Hide"),
        Binding("r", "restart_session", "Restart Session"),
        Binding("p", "pause_resume_session", "Pause/Resume Timer"),
        Binding("shift+s", "start_game", "Start Game Timer"),
        Binding("e", "edit_stats", "Edit Stats"),
        Binding("s", "set_rank", "Set Rank"),
        Binding("t", "set_season_start", "Set Season Start"),
        Binding("n", "add_game_notes", "Add Game Notes"),
        Binding("ctrl+n", "view_all_notes", "View All Notes"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("?", "help", "Help"),
    ]
    
    def __init__(self, state_manager: StateManager):
        super().__init__()
        self.state_manager = state_manager
        self.app_data = state_manager.load_state()
    
    def compose(self) -> ComposeResult:
        with Container():
            yield TopPanel(self.app_data).add_class("top-panel")
            
            with Container(id="main-content"):
                yield RankProgressPanel(self.app_data).add_class("left-panel")
                yield StatsPanel(self.app_data).add_class("right-panel")
            
            yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the app on mount."""
        # Create timer for status updates after app is mounted
        self.set_interval(1.0, self.update_status)
        self.update_status()
    
    def update_status(self) -> None:
        """Update top panel and status."""
        try:
            top_panel = self.query_one(TopPanel)
            top_panel.update_display()
        except:
            pass  # Ignore if not found during startup
        
        # Update timer-based elements in stats panel
        try:
            self._update_session_timers()
        except:
            pass  # Ignore if not found during startup
        
        # Save state periodically
        self.state_manager.save_state(self.app_data)
    
    def _update_session_timers(self) -> None:
        """Update session duration and last result timers."""
        try:
            # Find session section and update it
            session_section = self.query_one("#session-section", Static)
            stats = self.app_data.stats
            format_name = self.app_data.current_format.value.upper()
            
            # Session timing (active time only)
            duration_text = "00m 00s"
            pause_status = ""
            if stats.session_start_time:
                duration = stats.get_active_session_duration()
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                if hours > 0:
                    duration_text = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
                elif minutes > 0:
                    duration_text = f"{minutes:02d}m {seconds:02d}s"
                else:
                    duration_text = f"00m {seconds:02d}s"
                
                # Add pause indicator
                if stats.session_paused:
                    pause_status = " ⏸️ PAUSED"
            
            
            # Format start time safely
            start_time = "Not set"
            if stats.session_start_time:
                try:
                    if isinstance(stats.session_start_time, str):
                        session_start = datetime.fromisoformat(stats.session_start_time)
                    else:
                        session_start = stats.session_start_time
                    start_time = session_start.strftime("%I:%M %p")
                except:
                    start_time = "Invalid time"
            
            # Streak info
            current_streak_text = f"{stats.current_win_streak} / L{stats.current_loss_streak}"
            
            # Time since last result - show both real and active time
            last_result_text = "No games yet"
            if stats.last_result_time:
                real_seconds, active_seconds = stats.get_time_since_last_result()
                
                # Format real time
                real_minutes = real_seconds // 60
                real_secs = real_seconds % 60
                real_text = f"{real_minutes:02d}m {real_secs:02d}s"
                
                # Format active time 
                active_minutes = active_seconds // 60
                active_secs = active_seconds % 60
                active_text = f"{active_minutes:02d}m {active_secs:02d}s"
                
                # Show both if different, otherwise just one
                if real_seconds != active_seconds:
                    last_result_text = f"{real_text} ago ({active_text} active)"
                else:
                    last_result_text = f"{real_text} ago"
            
            # Game timer info
            game_timer_text = ""
            avg_game_text = ""
            if stats.game_start_time:
                game_seconds = int(stats.get_current_game_duration())
                game_minutes = game_seconds // 60
                game_secs = game_seconds % 60
                game_timer_text = f"  Current: {game_minutes:02d}m {game_secs:02d}s ⏰"
            
            if stats.game_durations:
                avg_seconds = int(stats.get_average_game_duration())
                avg_minutes = avg_seconds // 60
                avg_secs = avg_seconds % 60
                avg_game_text = f"Avg Game: [{avg_minutes:02d}m {avg_secs:02d}s]  "
            
            session_content = f"""📊 CURRENT SESSION [{format_name}]
Started:  [{start_time}]  Duration: {duration_text}{pause_status}
Record:   [{stats.session_wins}W] - [{stats.session_losses}L]  {stats.get_session_win_rate():.1f}%
Streaks:  W{current_streak_text} (current)
{avg_game_text}Last: {last_result_text}{game_timer_text}"""
            
            session_section.update(session_content)
        except:
            pass  # Ignore if section not found
    
    def _is_goal_attained(self, current_rank: ManualRank, goal_tier, goal_division) -> bool:
        """Check if the session goal has been attained."""
        if not goal_tier:
            return False
            
        # Handle mythic goal
        if goal_tier == RankTier.MYTHIC or str(goal_tier) == "Mythic":
            return current_rank.is_mythic()
            
        # Compare tier and division
        current_tier_str = current_rank.tier.value if hasattr(current_rank.tier, 'value') else str(current_rank.tier)
        goal_tier_str = goal_tier.value if hasattr(goal_tier, 'value') else str(goal_tier)
        
        if current_tier_str != goal_tier_str:
            return False
            
        # Same tier - compare division (lower division number = higher rank)
        return current_rank.division <= goal_division
    
    def action_add_win(self) -> None:
        """Add a win to the session."""
        # Check goal status before the win
        stats = self.app_data.stats
        current_rank = self.app_data.get_current_rank()
        was_goal_achieved = self._is_goal_attained(current_rank, stats.session_goal_tier, stats.session_goal_division)
        
        # Update rank
        new_rank = current_rank.add_win()
        self.app_data.set_current_rank(new_rank)
        
        # End game timer and record duration
        game_duration = self.app_data.stats.end_game_timer()
        
        # Update stats
        self.app_data.stats.add_win()
        
        # Check if goal was just achieved
        if not was_goal_achieved and stats.session_goal_tier:
            is_goal_achieved_now = self._is_goal_attained(new_rank, stats.session_goal_tier, stats.session_goal_division)
            if is_goal_achieved_now:
                # Goal just achieved!
                goal_name = "Mythic" if stats.session_goal_tier == RankTier.MYTHIC else f"{stats.session_goal_tier.value} {stats.session_goal_division}"
                self.notify(f"🎉 SESSION GOAL ACHIEVED: {goal_name}! 🎉", severity="success")
        
        # Check for milestones after win
        self._check_milestones(new_rank, current_rank)
        
        # Refresh display
        self.refresh_panels()
    
    def action_add_loss(self) -> None:
        """Add a loss to the session."""
        # Update rank
        current_rank = self.app_data.get_current_rank()
        new_rank = current_rank.add_loss()
        self.app_data.set_current_rank(new_rank)
        
        # End game timer and record duration
        game_duration = self.app_data.stats.end_game_timer()
        
        # Update stats
        self.app_data.stats.add_loss()
        
        # Refresh display
        self.refresh_panels()
    
    def action_switch_format(self) -> None:
        """Switch between BO1, BO3, and Limited."""
        # Cycle through format types
        if self.app_data.current_format == FormatType.CONSTRUCTED_BO1:
            self.app_data.current_format = FormatType.CONSTRUCTED_BO3
            new_format = "BO3"
        elif self.app_data.current_format == FormatType.CONSTRUCTED_BO3:
            self.app_data.current_format = FormatType.LIMITED
            new_format = "LIMITED"
        else:  # LIMITED
            self.app_data.current_format = FormatType.CONSTRUCTED_BO1
            new_format = "BO1"
        
        # Immediately update just the format column
        try:
            format_widget = self.query_one(".top-format", Static)
            format_widget.update(f"📊 {new_format}")
        except:
            pass
        
        # Force immediate update of everything
        self.refresh_panels()
        
        # Also call update_status to ensure top panel updates
        self.update_status()
    
    def action_set_goal(self) -> None:
        """Set session goal rank via modal."""
        current_rank = self.app_data.get_current_rank()
        
        # Create and push the goal setting modal
        modal = SetGoalModal(current_rank, self.app_data.current_format, self.app_data.stats)
        
        def handle_result(result):
            if result is not None:
                if result == (None, None):
                    # Clear goal
                    self.app_data.stats.session_goal_tier = None
                    self.app_data.stats.session_goal_division = None
                else:
                    # Set new goal
                    self.app_data.stats.session_goal_tier = result[0]
                    self.app_data.stats.session_goal_division = result[1]
                self.refresh_panels()
        
        # Push screen and handle result when dismissed
        self.push_screen(modal, handle_result)
    
    def action_set_season_start(self) -> None:
        """Set season start rank via modal."""
        current_rank = self.app_data.get_current_rank()
        
        # Create and push the season start rank modal
        modal = SetRankModal(current_rank, self.app_data.current_format, modal_title="Set Season Start Rank")
        
        def handle_result(result):
            if result:
                # Update the season start rank
                self.app_data.stats.season_start_rank = result
                self.refresh_panels()
        
        # Push screen and handle result when dismissed
        self.push_screen(modal, handle_result)
    
    def action_add_game_notes(self) -> None:
        """Add detailed game notes with optional result application."""
        modal = GameNotesModal()
        
        def handle_result(result):
            if result:
                # Save the note to session stats
                if not hasattr(self.app_data.stats, 'game_notes') or self.app_data.stats.game_notes is None:
                    self.app_data.stats.game_notes = []
                
                # Add note to the list
                note_entry = {
                    "id": len(self.app_data.stats.game_notes) + 1,
                    "timestamp": result['timestamp'],
                    "result": result['result'],
                    "play_draw": result['play_draw'],
                    "opponent_deck": result['opponent_deck'],
                    "notes": result['notes']
                }
                self.app_data.stats.game_notes.append(note_entry)
                
                # Save state
                self.state_manager.save_state(self.app_data)
                
                # Show summary toast
                note_summary = f"{result['play_draw']}"
                if result['opponent_deck']:
                    note_summary += f" vs {result['opponent_deck']}"
                
                self.notify(f"Note saved: {note_summary}", severity="success")
                self.refresh_panels()
        
        self.push_screen(modal, handle_result)
    
    def action_view_all_notes(self) -> None:
        """View and edit all game notes."""
        if not hasattr(self.app_data.stats, 'game_notes') or not self.app_data.stats.game_notes:
            self.notify("No game notes found!", severity="warning")
            return
        
        # Create the notes manager modal
        manager_modal = NotesManagerModal(self.app_data.stats.game_notes)
        
        def handle_manager_result(result):
            if result in ["updated", "deleted"]:
                # Save state and refresh display
                self.state_manager.save_state(self.app_data)
                self.refresh_panels()
                
                action_text = "updated" if result == "updated" else "deleted"
                self.notify(f"Note {action_text} successfully!", severity="success")
        
        self.push_screen(manager_modal, handle_manager_result)
    
    def action_edit_stats(self) -> None:
        """Edit session and season statistics."""
        modal = EditStatsModal(self.app_data.stats)
        
        def handle_result(result):
            if result == "saved":
                self.refresh_panels()
                self.state_manager.save_state(self.app_data)
                # Debug notification showing what was saved
                stats = self.app_data.stats
                self.notify(f"Stats updated! Best: W{stats.best_win_streak}, Worst: L{stats.worst_loss_streak}", severity="success")
        
        self.push_screen(modal, handle_result)
    
    def action_toggle_mythic(self) -> None:
        """Toggle mythic progress display."""
        self.app_data.show_mythic_progress = not self.app_data.show_mythic_progress
        self.refresh_panels()
    
    def action_collapse_tiers(self) -> None:
        """Toggle auto-collapse mode for completed tiers."""
        # Toggle auto-collapse mode
        self.app_data.auto_collapse_mode = not self.app_data.auto_collapse_mode
        
        current_rank = self.app_data.get_current_rank()
        tier_order = list(RankTier)[:-1]  # Exclude Mythic
        
        if self.app_data.auto_collapse_mode:
            # Enable auto-collapse: collapse all currently completed tiers
            if current_rank.is_mythic():
                completed_tiers = tier_order
            else:
                current_tier_idx = tier_order.index(current_rank.tier)
                completed_tiers = tier_order[:current_tier_idx]
            
            for tier in completed_tiers:
                if tier not in self.app_data.collapsed_tiers:
                    self.app_data.collapsed_tiers.append(tier)
        else:
            # Disable auto-collapse: uncollapse all tiers
            self.app_data.collapsed_tiers.clear()
        
        self.refresh_panels()
    
    def action_hide_tiers(self) -> None:
        """Toggle auto-hide mode for completed tiers completely."""
        # Toggle auto-hide mode
        self.app_data.auto_hide_mode = not self.app_data.auto_hide_mode
        
        current_rank = self.app_data.get_current_rank()
        tier_order = list(RankTier)[:-1]  # Exclude Mythic
        
        if self.app_data.auto_hide_mode:
            # Enable auto-hide: hide all currently completed tiers
            if current_rank.is_mythic():
                completed_tiers = tier_order
            else:
                current_tier_idx = tier_order.index(current_rank.tier)
                completed_tiers = tier_order[:current_tier_idx]
            
            for tier in completed_tiers:
                if tier not in self.app_data.hidden_tiers:
                    self.app_data.hidden_tiers.append(tier)
        else:
            # Disable auto-hide: unhide all tiers
            self.app_data.hidden_tiers.clear()
        
        self.refresh_panels()
    
    def action_restart_session(self) -> None:
        """Restart current session (same as reset)."""
        modal = ConfirmationModal("Restart session? This will reset wins/losses and session timer.")
        
        def handle_restart_result(result):
            if result:
                current_rank = self.app_data.get_current_rank()
                # Complete current session before resetting
                self.app_data.stats.complete_current_session(current_rank, self.app_data.current_format)
                self.app_data.stats.reset_session(current_rank)
                self.refresh_panels()
        
        self.push_screen(modal, handle_restart_result)
    
    def action_pause_resume_session(self) -> None:
        """Pause or resume the session timer."""
        stats = self.app_data.stats
        
        if stats.session_paused:
            # Resume the session
            stats.resume_session()
            self.notify("Session timer resumed", severity="success")
        else:
            # Pause the session
            if stats.session_start_time:
                stats.pause_session()
                self.notify("Session timer paused", severity="info")
            else:
                self.notify("No active session to pause", severity="warning")
        
        self.refresh_panels()
    
    def _check_milestones(self, new_rank: ManualRank, old_rank: ManualRank) -> None:
        """Check for various milestone achievements and show celebratory toasts."""
        stats = self.app_data.stats
        
        # 1. TIER PROMOTION MILESTONES
        self._check_tier_promotions(new_rank, old_rank)
        
        # 2. WIN COUNT MILESTONES (Session)
        self._check_win_milestones(stats.session_wins, "SESSION")
        
        # 3. WIN COUNT MILESTONES (Season) 
        self._check_win_milestones(stats.season_wins, "SEASON")
        
        # 4. WIN RATE MILESTONES
        self._check_winrate_milestones(stats)
        
        # Update milestone tracking
        stats.last_session_win_rate = stats.get_session_win_rate()
        stats.last_season_win_rate = stats.get_season_win_rate()
    
    def _check_tier_promotions(self, new_rank: ManualRank, old_rank: ManualRank) -> None:
        """Check for tier promotions and show celebration toasts."""
        tier_order = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Mythic"]
        
        old_tier_name = old_rank.tier.value if hasattr(old_rank.tier, 'value') else str(old_rank.tier)
        new_tier_name = new_rank.tier.value if hasattr(new_rank.tier, 'value') else str(new_rank.tier)
        
        if old_tier_name != new_tier_name:
            try:
                old_tier_idx = tier_order.index(old_tier_name)
                new_tier_idx = tier_order.index(new_tier_name)
                
                if new_tier_idx > old_tier_idx:
                    # Tier promotion!
                    if new_tier_name == "Mythic":
                        self.notify("🏆 MYTHIC ACHIEVED! Welcome to the top tier! 🏆", severity="success")
                    else:
                        self.notify(f"⬆️ TIER PROMOTION: Welcome to {new_tier_name}! ⬆️", severity="success")
            except ValueError:
                pass  # Unknown tier names
    
    def _check_win_milestones(self, win_count: int, scope: str) -> None:
        """Check for win count milestones (10, 25, 50, 100, 200+ wins)."""
        milestones = [10, 25, 50, 100, 200, 300, 500, 750, 1000]
        
        for milestone in milestones:
            if win_count == milestone:
                if milestone >= 500:
                    self.notify(f"🔥 {milestone} {scope} WINS! Absolute legend! 🔥", severity="success")
                elif milestone >= 200:
                    self.notify(f"⚡ {milestone} {scope} WINS! Incredible dedication! ⚡", severity="success")
                elif milestone >= 100:
                    self.notify(f"💪 {milestone} {scope} WINS! Century achieved! 💪", severity="success")
                elif milestone >= 50:
                    self.notify(f"🎯 {milestone} {scope} WINS! Halfway to 100! 🎯", severity="success")
                else:
                    self.notify(f"🎊 {milestone} {scope} WINS! Nice milestone! 🎊", severity="success")
                break
    
    def _check_winrate_milestones(self, stats: SessionStats) -> None:
        """Check for win rate threshold achievements."""
        session_rate = stats.get_session_win_rate()
        season_rate = stats.get_season_win_rate()
        
        # Session win rate milestones - check highest thresholds first
        if stats.session_wins + stats.session_losses >= 10:  # Only after meaningful sample
            for threshold in [80.0, 75.0, 70.0, 65.0, 60.0, 55.0, 50.0]:
                if session_rate >= threshold and stats.last_session_win_rate < threshold:
                    if threshold >= 75.0:
                        self.notify(f"🔥 SESSION {threshold:.0f}%+ WIN RATE! Dominating! 🔥", severity="success")
                    elif threshold >= 65.0:
                        self.notify(f"⭐ SESSION {threshold:.0f}%+ WIN RATE! Excellent! ⭐", severity="success")
                    else:
                        self.notify(f"📈 SESSION {threshold:.0f}%+ WIN RATE! On fire! 📈", severity="success")
                    break
        
        # Season win rate milestones - check highest thresholds first  
        if stats.season_wins + stats.season_losses >= 50:  # Only after meaningful sample
            for threshold in [75.0, 70.0, 65.0, 60.0, 55.0, 50.0]:
                if season_rate >= threshold and stats.last_season_win_rate < threshold:
                    if threshold >= 70.0:
                        self.notify(f"👑 SEASON {threshold:.0f}%+ WIN RATE! Elite performance! 👑", severity="success")
                    elif threshold >= 60.0:
                        self.notify(f"🌟 SEASON {threshold:.0f}%+ WIN RATE! Strong climbing! 🌟", severity="success")
                    else:
                        self.notify(f"📊 SEASON {threshold:.0f}%+ WIN RATE! Positive record! 📊", severity="success")
                    break
    
    def action_start_game(self) -> None:
        """Start a new game timer."""
        stats = self.app_data.stats
        
        if stats.game_start_time:
            # Game already in progress, ask to restart
            modal = ConfirmationModal("Game timer already running. Restart timer?")
            
            def handle_restart_game(result):
                if result:
                    stats.start_game_timer()
                    self.notify("Game timer restarted", severity="info")
                    self.refresh_panels()
            
            self.push_screen(modal, handle_restart_game)
        else:
            # Start new game timer
            stats.start_game_timer()
            self.notify("Game timer started", severity="success")
            self.refresh_panels()
    
    def action_help(self) -> None:
        """Show help information."""
        help_text = """MTGA Manual Tracker Help

Keyboard Shortcuts:
W/+ - Add win       L/- - Add loss
F - Switch format (BO1/BO3/Limited)  
G - Set session goal    T - Set season start rank
E - Edit stats (streaks, session start)
N - Add game notes    Ctrl+N - View all notes
M - Toggle mythic progress
C - Collapse tiers      H - Hide tiers
R - Restart session     P - Pause/Resume timer
Shift+S - Start game    S - Set rank manually   
Ctrl+Q - Quit

Manual Editing:
Click any [bracketed] value to edit inline
Click rank bars to set exact position
ESC to cancel editing

Press any key to close this help."""
        
        self.push_screen(ConfirmationModal(help_text))

    def action_set_rank(self) -> None:
        """Set rank manually via modal with dropdowns."""
        current_rank = self.app_data.get_current_rank()
        
        # Create and push the modal
        modal = SetRankModal(current_rank, self.app_data.current_format)
        
        def handle_result(result):
            if result:
                # Check goal status before the change
                stats = self.app_data.stats
                current_rank = self.app_data.get_current_rank()
                was_goal_achieved = self._is_goal_attained(current_rank, stats.session_goal_tier, stats.session_goal_division)
                
                # Update the rank and refresh
                self.app_data.set_current_rank(result)
                
                # Check if goal was just achieved through manual rank setting
                if not was_goal_achieved and stats.session_goal_tier:
                    is_goal_achieved_now = self._is_goal_attained(result, stats.session_goal_tier, stats.session_goal_division)
                    if is_goal_achieved_now:
                        # Goal just achieved!
                        goal_name = "Mythic" if stats.session_goal_tier == RankTier.MYTHIC else f"{stats.session_goal_tier.value} {stats.session_goal_division}"
                        self.notify(f"🎉 SESSION GOAL ACHIEVED: {goal_name}! 🎉", severity="success")
                
                self.refresh_panels()
        
        # Push screen and handle result when dismissed
        self.push_screen(modal, handle_result)
    
    def refresh_panels(self) -> None:
        """Refresh all panels with current data."""
        # Update the top panel
        self.update_status()
        
        # Force refresh of rank progress panel by removing and re-adding
        try:
            main_content = self.query_one("#main-content")
            # Remove existing panels
            left_panel = self.query_one(".left-panel")
            right_panel = self.query_one(".right-panel")
            left_panel.remove()
            right_panel.remove()
            
            # Add new panels with updated data
            main_content.mount(RankProgressPanel(self.app_data).add_class("left-panel"))
            main_content.mount(StatsPanel(self.app_data).add_class("right-panel"))
        except:
            pass  # Ignore if panels not found
    
    def on_exit(self) -> None:
        """Save state before exit."""
        self.state_manager.save_state(self.app_data)

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="MTGA Mythic TUI Session Tracker (Manual)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                           # Run with default settings
  %(prog)s --data-dir ~/my-data/     # Use custom data directory
  %(prog)s --no-save                 # Don't save state (fresh each run)
  %(prog)s --format Limited          # Start in Limited format
"""
    )
    
    parser.add_argument(
        "--data-dir", 
        type=Path,
        help="Directory for saving application data (default: ~/.local/share/mtga-manual-tracker/)"
    )
    
    parser.add_argument(
        "--no-save",
        action="store_true", 
        help="Don't save/load application state"
    )
    
    parser.add_argument(
        "--format",
        choices=["Constructed", "Limited"],
        default="Constructed",
        help="Starting format (default: Constructed)"
    )
    
    args = parser.parse_args()
    
    # Create state manager
    state_manager = StateManager(
        data_dir=args.data_dir,
        save_enabled=not args.no_save
    )
    
    # Create and run app
    app = ManualTUIApp(state_manager)
    
    # Set initial format if specified
    if args.format == "Limited":
        app.app_data.current_format = FormatType.LIMITED
    
    try:
        app.run()
    finally:
        # Ensure state is saved on exit
        if not args.no_save:
            state_manager.save_state(app.app_data)

if __name__ == "__main__":
    main()