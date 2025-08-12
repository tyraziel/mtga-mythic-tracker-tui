#!/usr/bin/env python3
"""
Test script for MTG Arena tracker models.
"""
from datetime import datetime
from src.models.rank import Rank, RankTier, FormatType
from src.models.game import Game, GameResult, PlayOrder, GameStats


def test_rank_system():
    """Test rank system functionality."""
    print("=== Testing Rank System ===")
    
    # Test basic rank creation
    rank = Rank(tier=RankTier.GOLD, division=3, pips=4, max_pips=6)
    print(f"Created rank: {rank}")
    
    # Test pip addition and promotion
    promoted_rank = rank.add_pips(3)  # Should promote to Gold Tier 2
    print(f"After +3 pips: {promoted_rank}")
    
    # Test pip removal and demotion
    demoted_rank = promoted_rank.remove_pips(8)  # Should demote
    print(f"After -8 pips: {demoted_rank}")
    
    # Test Mythic rank
    mythic_rank = Rank(tier=RankTier.MYTHIC, mythic_percentage=85.5)
    print(f"Mythic rank: {mythic_rank}")
    
    # Test Bronze protection
    bronze_rank = Rank(tier=RankTier.BRONZE, division=4, pips=2)
    bronze_after_loss = bronze_rank.remove_pips(5)  # Should not demote
    print(f"Bronze after big loss: {bronze_after_loss}")
    
    # Test tier floor protection (Gold can't drop to Silver)
    gold_bottom = Rank(tier=RankTier.GOLD, division=4, pips=0)
    gold_after_losses = gold_bottom.remove_pips(10)  # Should stay in Gold
    print(f"Gold at bottom after losses: {gold_after_losses}")
    
    # Test division dropping within tier (Gold 3 → Gold 4)
    print("--- Division Dropping Tests ---")
    
    # Test Gold 2 → Gold 3 demotion protection
    gold_2 = Rank(tier=RankTier.GOLD, division=2, pips=0)
    print(f"Starting: {gold_2}")
    
    for i in range(1, 5):
        gold_2 = gold_2.remove_pips(1)
        status = "DEMOTED!" if gold_2.division == 3 else "protected"
        print(f"Loss {i}: {gold_2} (losses: {gold_2.losses_at_zero}) - {status}")
    
    print()
    
    # Test Platinum 3 → Platinum 4 demotion protection
    plat_3 = Rank(tier=RankTier.PLATINUM, division=3, pips=0)
    print(f"Starting: {plat_3}")
    
    for i in range(1, 5):
        plat_3 = plat_3.remove_pips(1)
        status = "DEMOTED!" if plat_3.division == 4 else "protected"
        print(f"Loss {i}: {plat_3} (losses: {plat_3.losses_at_zero}) - {status}")
    
    print()
    
    # Test that winning resets protection counter
    test_rank = Rank(tier=RankTier.DIAMOND, division=1, pips=0, losses_at_zero=2)
    print(f"Before win: {test_rank} (losses: {test_rank.losses_at_zero})")
    after_win = test_rank.add_pips(1)
    print(f"After win: {after_win} (losses: {after_win.losses_at_zero}) - counter reset!")
    
    print()


def test_game_tracking():
    """Test game tracking functionality."""
    print("=== Testing Game Tracking ===")
    
    # Create ranks for before/after
    rank_before = Rank(tier=RankTier.PLATINUM, division=2, pips=4)
    rank_after = Rank(tier=RankTier.PLATINUM, division=2, pips=6)
    
    # Create a game
    game = Game(
        result=GameResult.WIN,
        play_order=PlayOrder.DRAW,
        format_type=FormatType.CONSTRUCTED,
        player_deck="Esper Control",
        opponent_deck="Mono-Red Aggro",
        notes="Close game, stabilized at 3 life",
        rank_before=rank_before,
        rank_after=rank_after,
        pips_gained=2
    )
    
    print(f"Game: {game.result.value} on the {game.play_order.value}")
    print(f"Decks: {game.player_deck} vs {game.opponent_deck}")
    print(f"Rank change: {game.rank_change_str()}")
    print(f"Was promotion: {game.was_promotion()}")
    print(f"Notes: {game.notes}")
    
    print()


def test_game_stats():
    """Test game statistics functionality."""
    print("=== Testing Game Stats ===")
    
    stats = GameStats()
    
    # Add some test games
    games = [
        Game(result=GameResult.WIN, play_order=PlayOrder.PLAY, format_type=FormatType.CONSTRUCTED),
        Game(result=GameResult.LOSS, play_order=PlayOrder.DRAW, format_type=FormatType.CONSTRUCTED),
        Game(result=GameResult.WIN, play_order=PlayOrder.DRAW, format_type=FormatType.CONSTRUCTED),
        Game(result=GameResult.WIN, play_order=PlayOrder.PLAY, format_type=FormatType.CONSTRUCTED),
        Game(result=GameResult.LOSS, play_order=PlayOrder.PLAY, format_type=FormatType.CONSTRUCTED),
    ]
    
    for game in games:
        stats.update_with_game(game)
    
    print(f"Total games: {stats.total_games}")
    print(f"Overall win rate: {stats.win_rate():.1f}%")
    print(f"Play win rate: {stats.play_win_rate():.1f}%")
    print(f"Draw win rate: {stats.draw_win_rate():.1f}%")
    print(f"Play/Draw split: {stats.play_games}/{stats.draw_games}")
    
    print()


def main():
    """Run all tests."""
    print("MTG Arena Tracker - Model Testing")
    print("=" * 40)
    
    try:
        test_rank_system()
        test_game_tracking()
        test_game_stats()
        
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()