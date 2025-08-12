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
from textual.widgets import Static, Input, Button, Label
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message

# === MODELS ===

class FormatType(str, Enum):
    """MTG Arena format types."""
    CONSTRUCTED = "Constructed"
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
    format_type: FormatType = FormatType.CONSTRUCTED
    
    @property
    def max_pips(self) -> int:
        """Get max pips per division based on format."""
        if self.format_type == FormatType.CONSTRUCTED:
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
            
        # Determine pips gained per win based on tier
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
                    new_pips = 0
        
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
            
        # Bronze/Silver can't lose pips
        if self.tier in [RankTier.BRONZE, RankTier.SILVER]:
            return self
            
        # Other tiers lose 1 pip
        new_pips = max(0, self.pips - 1)
        
        # Handle demotion within tier (simplified - no demotion protection for manual)
        new_division = self.division
        if new_pips < 0 and new_division and new_division < 4:
            new_division += 1
            new_pips = self.max_pips - 1
        
        return ManualRank(
            tier=self.tier,
            division=new_division,
            pips=new_pips,
            format_type=self.format_type
        )
    
    def __str__(self) -> str:
        """String representation of rank."""
        if self.is_mythic():
            if self.mythic_rank:
                return f"Mythic #{self.mythic_rank}"
            return f"Mythic {self.mythic_percentage:.1f}%"
        return f"{self.tier.value} {self.division} ({self.pips}/{self.max_pips})"

@dataclass  
class SessionStats:
    """Session and season statistics."""
    # Current session
    session_wins: int = 0
    session_losses: int = 0
    session_start_time: Optional[datetime] = None
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
    
    def add_loss(self):
        """Add a loss to session and update streaks."""
        self.session_losses += 1
        self.season_losses += 1
        self.current_loss_streak += 1
        self.current_win_streak = 0
        self.worst_loss_streak = max(self.worst_loss_streak, self.current_loss_streak)
    
    def reset_session(self):
        """Reset session stats but keep season totals."""
        self.session_wins = 0
        self.session_losses = 0
        self.session_start_time = datetime.now()
        self.current_win_streak = 0
        self.current_loss_streak = 0

@dataclass
class AppData:
    """Complete application state."""
    constructed_rank: ManualRank
    limited_rank: ManualRank
    current_format: FormatType
    stats: SessionStats
    show_mythic_progress: bool = True
    collapsed_tiers: List[RankTier] = None
    
    def __post_init__(self):
        if self.collapsed_tiers is None:
            self.collapsed_tiers = []
    
    def get_current_rank(self) -> ManualRank:
        """Get rank for current format."""
        if self.current_format == FormatType.CONSTRUCTED:
            return self.constructed_rank
        else:
            return self.limited_rank
    
    def set_current_rank(self, rank: ManualRank):
        """Set rank for current format."""
        if self.current_format == FormatType.CONSTRUCTED:
            self.constructed_rank = rank
        else:
            self.limited_rank = rank

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
            
            # Reconstruct objects
            constructed_rank = ManualRank(**data['constructed_rank'])
            limited_rank = ManualRank(**data['limited_rank'])
            
            # Handle SessionStats with potential missing fields
            stats_data = data['stats']
            stats = SessionStats(**stats_data)
            
            return AppData(
                constructed_rank=constructed_rank,
                limited_rank=limited_rank,
                current_format=FormatType(data['current_format']),
                stats=stats,
                show_mythic_progress=data.get('show_mythic_progress', True),
                collapsed_tiers=[RankTier(t) for t in data.get('collapsed_tiers', [])]
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
                'collapsed_tiers': [t.value for t in app_data.collapsed_tiers]
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
                format_type=FormatType.CONSTRUCTED
            ),
            limited_rank=ManualRank(
                tier=RankTier.BRONZE,
                division=4, 
                pips=0,
                format_type=FormatType.LIMITED
            ),
            current_format=FormatType.CONSTRUCTED,
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
            'session_start_time', 'season_end_date'
        ]
        
        def convert_iso_string(obj, parent_key=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    obj[k] = convert_iso_string(v, k)
            elif isinstance(obj, str) and parent_key in datetime_fields:
                try:
                    return datetime.fromisoformat(obj)
                except:
                    return None
            return obj
        
        for key, value in data.items():
            data[key] = convert_iso_string(value, key)

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
            # Left section - Season & Format
            yield Static("🕐 Season: Loading...\n📊 Format: CONSTRUCTED", classes="top-left")
            
            # Center section - Current Rank & Progress
            yield Static("📍 Current: Loading...\n🎯 Progress: Loading...", classes="top-center")
            
            # Right section - Session Info
            yield Static("📊 Session: 0W-0L\n⏱️ Duration: 0m", classes="top-right")
    
    def update_display(self):
        """Update top panel display."""
        current_rank = self.app_data.get_current_rank()
        format_name = self.app_data.current_format.value.upper()
        stats = self.app_data.stats
        
        # LEFT SECTION - Season countdown and format
        season_text = "Season: --"
        if stats.season_end_date:
            time_left = stats.season_end_date - datetime.now()
            if time_left.total_seconds() > 0:
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                if days > 0:
                    season_text = f"Season: {days}d {hours}h {minutes}m"
                else:
                    season_text = f"Season: {hours}h {minutes}m"
            else:
                season_text = "Season: ENDED"
        
        left_content = f"🕐 {season_text}\n📊 Format: {format_name}"
        
        # CENTER SECTION - Current rank and progress
        rank_text = f"{current_rank.tier.value} {current_rank.division} ({current_rank.pips}/{current_rank.max_pips})"
        if current_rank.is_mythic():
            if current_rank.mythic_rank:
                rank_text = f"Mythic #{current_rank.mythic_rank}"
            else:
                rank_text = f"Mythic {current_rank.mythic_percentage:.1f}%"
        
        bars_remaining = current_rank.get_total_bars_remaining_to_mythic()
        if bars_remaining > 0 and self.app_data.show_mythic_progress:
            progress_text = f"Bars to Mythic: {bars_remaining}"
        else:
            progress_text = "MYTHIC ACHIEVED!" if current_rank.is_mythic() else "Progress tracking hidden"
            
        center_content = f"📍 Current: {rank_text}\n🎯 {progress_text}"
        
        # RIGHT SECTION - Session info
        session_win_rate = stats.get_session_win_rate()
        duration_text = "0m"
        if stats.session_start_time:
            duration = datetime.now() - stats.session_start_time
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            if hours > 0:
                duration_text = f"{hours}h {minutes}m"
            else:
                duration_text = f"{minutes}m"
        
        right_content = f"📊 Session: {stats.session_wins}W-{stats.session_losses}L ({session_win_rate:.0f}%)\n⏱️ Duration: {duration_text}"
        
        # Update the three sections
        try:
            left_widget = self.query_one(".top-left", Static)
            left_widget.update(left_content)
            
            center_widget = self.query_one(".top-center", Static)
            center_widget.update(center_content)
            
            right_widget = self.query_one(".top-right", Static)
            right_widget.update(right_content)
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
            yield Static(f"─ Rank Progress [{format_name.upper()}] ─", classes="panel-header")
            yield Button("[F] Switch to Limited" if self.app_data.current_format == FormatType.CONSTRUCTED else "[F] Switch to Constructed", 
                        id="format-switch", classes="switch-button")
            yield Static("─" * 30, classes="separator")
            
            # Mythic display
            if current_rank.tier == RankTier.MYTHIC:
                yield self._create_mythic_display(current_rank)
            else:
                yield self._create_rank_bars()
            
            yield Static("─" * 30, classes="separator")
            yield Static("[Click any bar to set rank position]", classes="help-text")
            yield Static("[C] Collapse [H] Hide completed tiers", classes="help-text")
    
    def _create_mythic_display(self, rank: ManualRank) -> Static:
        """Create Mythic achievement display."""
        if rank.mythic_rank:
            current_text = f"Current: #{rank.mythic_rank}"
        else:
            current_text = f"Current: {rank.mythic_percentage:.1f}%"
        
        return Static(f"""🏆 MYTHIC ACHIEVED! 🏆

{current_text}

[H] Show Full Rank History""", classes="mythic-display")
    
    def _create_rank_bars(self) -> Static:
        """Create rank progression bars as a single text widget."""
        current_rank = self.app_data.get_current_rank()
        
        # Build text display
        lines = []
        
        # All rank tiers from Mythic down to Bronze
        tier_order = list(RankTier)
        tier_order.reverse()  # Mythic at top
        
        for tier in tier_order:
            if tier == RankTier.MYTHIC:
                lines.append("Mythic    [  ][  ][  ] 0%")
            else:
                # Check if this tier should be collapsed
                if tier in self.app_data.collapsed_tiers:
                    lines.append(f"{tier.value:<8} [████████████████] FULL")
                else:
                    # Show all 4 divisions for this tier
                    for div in range(1, 5):
                        bars = self._create_bar_display(tier, div, current_rank)
                        marker = " ←YOU" if (tier == current_rank.tier and div == current_rank.division) else ""
                        goal_marker = " ←GOAL" if self._is_goal_rank(tier, div) else ""
                        
                        lines.append(f"{tier.value} {div}    {bars}{marker}{goal_marker}")
        
        return Static("\n".join(lines), classes="rank-bars")
    
    def _create_bar_display(self, tier: RankTier, division: int, current_rank: ManualRank) -> str:
        """Create bar display for a specific tier/division."""
        max_pips = current_rank.max_pips
        bars = []
        
        # Determine if this position is filled based on current rank
        is_filled = self._is_position_filled(tier, division, current_rank)
        
        if is_filled:
            # All bars filled
            for _ in range(max_pips):
                bars.append("[██]")
        else:
            # Check if this is current position (partially filled)
            if tier == current_rank.tier and division == current_rank.division:
                for i in range(max_pips):
                    if i < current_rank.pips:
                        bars.append("[██]")
                    else:
                        bars.append("[  ]")
            else:
                # Empty bars
                for _ in range(max_pips):
                    bars.append("[  ]")
        
        return "".join(bars)
    
    def _is_position_filled(self, tier: RankTier, division: int, current_rank: ManualRank) -> bool:
        """Check if a rank position should be displayed as filled."""
        if current_rank.is_mythic():
            return True  # All positions below Mythic are filled
        
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
            
            # Control buttons
            yield Static("[W] +Win  [L] +Loss  [R] Reset Session", classes="controls")
            yield Static("[F] Format [G] Goal  [M] Toggle Mythic", classes="controls")
    
    def _create_goal_section(self) -> Static:
        """Create session goal section."""
        stats = self.app_data.stats
        if stats.session_goal_tier and stats.session_goal_division:
            goal_text = f"{stats.session_goal_tier.value} {stats.session_goal_division}"
            
            # Calculate bars away
            current_rank = self.app_data.get_current_rank()
            # Simplified - just show "X bars away!"
            return Static(f"🎯 SESSION GOAL: [{goal_text}] 4 bars away!", classes="goal-section")
        else:
            return Static("🎯 SESSION GOAL: [Not Set] [G] to set", classes="goal-section")
    
    def _create_session_section(self) -> Static:
        """Create current session stats."""
        stats = self.app_data.stats
        format_name = self.app_data.current_format.value.upper()
        
        # Session timing
        duration_text = "0m"
        if stats.session_start_time:
            duration = datetime.now() - stats.session_start_time
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            if hours > 0:
                duration_text = f"{hours}h {minutes}m"
            else:
                duration_text = f"{minutes}m"
        
        start_time = stats.session_start_time.strftime("%I:%M %p") if stats.session_start_time else "Not set"
        
        # Streak info
        if stats.current_win_streak > 0:
            streak_text = f"W{stats.current_win_streak}"
        elif stats.current_loss_streak > 0:
            streak_text = f"L{stats.current_loss_streak}"
        else:
            streak_text = "None"
        
        current_streak_text = f"{stats.current_win_streak} / L{stats.current_loss_streak}"
        
        return Static(f"""📊 CURRENT SESSION [{format_name}]
Started:  [{start_time}]  Duration: {duration_text}
Record:   [{stats.session_wins}W] - [{stats.session_losses}L]  {stats.get_session_win_rate():.1f}%
Streaks:  W{current_streak_text} (current)""", classes="session-section")
    
    def _create_season_section(self) -> Static:
        """Create season total stats."""
        stats = self.app_data.stats
        format_name = self.app_data.current_format.value.upper()
        
        start_rank = "Not set"
        if stats.season_start_rank:
            start_rank = f"{stats.season_start_rank.tier.value} {stats.season_start_rank.division} ({stats.season_start_rank.pips}/{stats.season_start_rank.max_pips})"
        
        return Static(f"""🏆 SEASON TOTAL [{format_name}]
Record:   [{stats.season_wins}W] - [{stats.season_losses}L]  {stats.get_season_win_rate():.1f}%
Best:     [W{stats.best_win_streak}]  Worst: [L{stats.worst_loss_streak}]
Started:  [{start_rank}]""", classes="season-section")
    
    def _create_history_section(self) -> Static:
        """Create session history section."""
        stats = self.app_data.stats
        
        return Static(f"""📈 SESSION HISTORY
Today:     {stats.session_wins}W-{stats.session_losses}L ({stats.get_session_win_rate():.1f}%) +0 bars
Yesterday: 0W-0L (0.0%) +0 bars
This Week: {stats.session_wins}W-{stats.session_losses}L ({stats.get_session_win_rate():.1f}%) +0 bars
Last Week: 0W-0L (0.0%) +0 bars
Best Day:  0W-0L (0.0%) +0 bars""", classes="history-section")

class ConfirmationModal(ModalScreen):
    """Modal dialog for confirmations."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.result = False
    
    def compose(self) -> ComposeResult:
        with Container(classes="modal-container"):
            yield Static(self.message, classes="modal-message")
            with Horizontal(classes="modal-buttons"):
                yield Button("Yes", id="confirm-yes", variant="success")
                yield Button("No", id="confirm-no", variant="error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.result = True
        else:
            self.result = False
        self.dismiss(self.result)

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
        background: $accent;
        color: $text;
        border: solid $primary;
        padding: 0 1;
    }
    
    .top-panel-layout {
        height: 100%;
    }
    
    .top-left, .top-center, .top-right {
        width: 33%;
        height: 100%;
        padding: 0 1;
        content-align: left middle;
    }
    
    .top-center {
        content-align: center middle;
    }
    
    .top-right {
        content-align: right middle;
    }
    
    #main-content {
        layout: horizontal;
    }
    
    .left-panel, .right-panel {
        width: 50%;
        border: solid $primary;
        margin: 1;
        padding: 1;
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
    """
    
    BINDINGS = [
        Binding("w", "add_win", "Add Win"),
        Binding("l", "add_loss", "Add Loss"),
        Binding("f", "switch_format", "Switch Format"),
        Binding("g", "set_goal", "Set Goal"),
        Binding("m", "toggle_mythic", "Toggle Mythic"),
        Binding("c", "collapse_tiers", "Collapse"),
        Binding("h", "hide_tiers", "Hide"),
        Binding("r", "reset_session", "Reset Session"),
        Binding("q", "quit", "Quit"),
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
            
            yield Static("[Tab] Switch Panels  [S]tart Session  [E]nd Session  [Q]uit  [?] Help").add_class("footer-controls")
    
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
        
        # Save state periodically
        self.state_manager.save_state(self.app_data)
    
    def action_add_win(self) -> None:
        """Add a win to the session."""
        # Update rank
        current_rank = self.app_data.get_current_rank()
        new_rank = current_rank.add_win()
        self.app_data.set_current_rank(new_rank)
        
        # Update stats
        self.app_data.stats.add_win()
        
        # Refresh display
        self.refresh_panels()
    
    def action_add_loss(self) -> None:
        """Add a loss to the session."""
        # Update rank
        current_rank = self.app_data.get_current_rank()
        new_rank = current_rank.add_loss()
        self.app_data.set_current_rank(new_rank)
        
        # Update stats
        self.app_data.stats.add_loss()
        
        # Refresh display
        self.refresh_panels()
    
    def action_switch_format(self) -> None:
        """Switch between Constructed and Limited."""
        if self.app_data.current_format == FormatType.CONSTRUCTED:
            self.app_data.current_format = FormatType.LIMITED
        else:
            self.app_data.current_format = FormatType.CONSTRUCTED
        
        self.refresh_panels()
    
    def action_set_goal(self) -> None:
        """Set session goal rank."""
        # For now, just cycle through some common goals
        current_rank = self.app_data.get_current_rank()
        if current_rank.tier == RankTier.PLATINUM and current_rank.division == 1:
            # Set goal to Diamond 4
            self.app_data.stats.session_goal_tier = RankTier.DIAMOND
            self.app_data.stats.session_goal_division = 4
        else:
            # Set goal to next division up
            if current_rank.division and current_rank.division > 1:
                self.app_data.stats.session_goal_tier = current_rank.tier
                self.app_data.stats.session_goal_division = current_rank.division - 1
        
        self.refresh_panels()
    
    def action_toggle_mythic(self) -> None:
        """Toggle mythic progress display."""
        self.app_data.show_mythic_progress = not self.app_data.show_mythic_progress
        self.refresh_panels()
    
    def action_collapse_tiers(self) -> None:
        """Collapse completed tiers."""
        # Add completed tiers to collapsed list
        current_rank = self.app_data.get_current_rank()
        tier_order = list(RankTier)[:-1]  # Exclude Mythic
        
        if not current_rank.is_mythic():
            current_tier_idx = tier_order.index(current_rank.tier)
            for i in range(current_tier_idx):
                tier = tier_order[i]
                if tier not in self.app_data.collapsed_tiers:
                    self.app_data.collapsed_tiers.append(tier)
        
        self.refresh_panels()
    
    def action_hide_tiers(self) -> None:
        """Hide completed tiers completely."""
        # Similar to collapse but more aggressive
        self.action_collapse_tiers()
    
    async def action_reset_session(self) -> None:
        """Reset current session with confirmation."""
        result = await self.push_screen_wait(
            ConfirmationModal("Reset current session? This will clear wins/losses but keep rank.")
        )
        
        if result:
            self.app_data.stats.reset_session()
            self.refresh_panels()
    
    def action_help(self) -> None:
        """Show help information."""
        help_text = """MTGA Manual Tracker Help

Keyboard Shortcuts:
W - Add win      L - Add loss
F - Switch format (Constructed/Limited)  
G - Set session goal
M - Toggle mythic progress
C - Collapse tiers    H - Hide tiers
R - Reset session     Q - Quit

Manual Editing:
Click any [bracketed] value to edit inline
Click rank bars to set exact position
ESC to cancel editing

Press any key to close this help."""
        
        self.push_screen(ConfirmationModal(help_text))
    
    def refresh_panels(self) -> None:
        """Refresh all panels with current data."""
        # For now, just trigger a status update
        self.update_status()
    
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