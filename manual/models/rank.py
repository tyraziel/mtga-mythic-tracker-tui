"""
Rank-related models for MTGA Manual TUI Tracker.

Contains FormatType, RankTier enums and ManualRank class with all rank progression logic.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
from datetime import datetime


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
    
    def get_bars_per_win(self) -> int:
        """Get the number of bars (pips) gained per win for this rank and format."""
        if self.format_type == FormatType.CONSTRUCTED_BO3:
            # BO3 is double the pips of BO1
            if self.tier in [RankTier.BRONZE, RankTier.SILVER, RankTier.GOLD]:
                return 4  # Double of 2
            elif self.tier in [RankTier.PLATINUM, RankTier.DIAMOND]:
                return 2  # Double of 1
            else:
                return 2
        else:
            # BO1 or Limited - standard progression
            if self.tier in [RankTier.BRONZE, RankTier.SILVER, RankTier.GOLD]:
                return 2
            elif self.tier in [RankTier.PLATINUM, RankTier.DIAMOND]:
                return 1
            else:
                return 1
    
    def is_boss_fight(self) -> bool:
        """Check if the next win would promote to the next tier (boss fight!)."""
        if self.is_mythic():
            return False  # Already at highest tier
        
        if self.division != 1:
            return False  # Must be in Division 1 to be close to tier promotion
        
        # Determine bars gained per win based on tier
        bars_per_win = self.get_bars_per_win()
        
        # Boss fight: when pips + bars_per_win >= max_pips (would promote to next tier)
        return self.pips + bars_per_win >= self.max_pips
    
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