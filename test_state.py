#!/usr/bin/env python3
"""
Test script for application state management.
"""
import tempfile
from pathlib import Path
from datetime import datetime

from src.core.state_manager import StateManager
from src.models.session import AppState, Session, SessionStatus, GameState
from src.models.game import Game, GameResult, PlayOrder
from src.models.rank import Rank, RankTier, FormatType


def test_basic_state_operations():
    """Test basic state management operations."""
    print("=== Testing Basic State Operations ===")
    
    # Create new state manager
    manager = StateManager()
    manager.disable_auto_save()  # Prevent file I/O during testing
    
    # Test initial state
    state = manager.state
    print(f"Initial state has active session: {state.has_active_session()}")
    print(f"Initial session ID: {state.current_session_id}")
    
    # Start a new session
    starting_rank = Rank(tier=RankTier.GOLD, division=2, pips=3)
    session = manager.start_session(FormatType.CONSTRUCTED, starting_rank)
    
    print(f"✅ Started session: {session.session_id}")
    print(f"✅ Session format: {session.format_type.value}")
    print(f"✅ Starting rank: {session.starting_rank}")
    print(f"✅ Has active session: {state.has_active_session()}")
    
    print()


def test_game_tracking():
    """Test game tracking within sessions."""
    print("=== Testing Game Tracking ===")
    
    manager = StateManager()
    manager.disable_auto_save()
    
    # Start session
    starting_rank = Rank(tier=RankTier.PLATINUM, division=3, pips=2)
    session = manager.start_session(FormatType.CONSTRUCTED, starting_rank)
    
    # Create test games
    rank_after_win = starting_rank.add_pips(2)
    game1 = Game(
        result=GameResult.WIN,
        play_order=PlayOrder.PLAY,
        format_type=FormatType.CONSTRUCTED,
        player_deck="Esper Control",
        opponent_deck="Mono-Red Aggro",
        notes="Good mulligan, stabilized early",
        rank_before=starting_rank,
        rank_after=rank_after_win,
        pips_gained=2
    )
    
    rank_after_loss = rank_after_win.remove_pips(1)
    game2 = Game(
        result=GameResult.LOSS,
        play_order=PlayOrder.DRAW,
        format_type=FormatType.CONSTRUCTED,
        player_deck="Esper Control",
        opponent_deck="Grixis Midrange",
        notes="Flooded out, drew 6 lands",
        rank_before=rank_after_win,
        rank_after=rank_after_loss,
        pips_gained=-1
    )
    
    # Add games to session
    success1 = manager.add_game(game1)
    success2 = manager.add_game(game2)
    
    print(f"✅ Game 1 added: {success1}")
    print(f"✅ Game 2 added: {success2}")
    print(f"✅ Session games: {len(session.games)}")
    print(f"✅ Session stats: {session.stats.wins}W-{session.stats.losses}L")
    print(f"✅ Win rate: {session.stats.win_rate():.1f}%")
    print(f"✅ Rank change: {session.get_rank_change()}")
    
    print()


def test_session_lifecycle():
    """Test complete session lifecycle."""
    print("=== Testing Session Lifecycle ===")
    
    manager = StateManager()
    manager.disable_auto_save()
    
    # Start session
    starting_rank = Rank(tier=RankTier.DIAMOND, division=1, pips=5)
    session = manager.start_session(FormatType.LIMITED, starting_rank)
    
    print(f"✅ Session started: {session.status.value}")
    print(f"✅ Start time: {session.start_time}")
    
    # Pause session
    manager.pause_session()
    print(f"✅ Session paused: {session.status.value}")
    
    # Resume session
    manager.resume_session()
    print(f"✅ Session resumed: {session.status.value}")
    
    # End session
    ended_session = manager.end_session()
    print(f"✅ Session ended: {ended_session.status.value}")
    print(f"✅ End time: {ended_session.end_time}")
    print(f"✅ Duration: {ended_session.get_duration_minutes()} minutes")
    print(f"✅ No active session: {not manager.state.has_active_session()}")
    
    print()


def test_live_game_state():
    """Test live game state tracking."""
    print("=== Testing Live Game State ===")
    
    manager = StateManager()
    manager.disable_auto_save()
    
    # Update live game state
    manager.update_live_game_state(
        is_in_game=True,
        turn_number=5,
        player_life=18,
        opponent_life=12,
        player_cards_in_hand=4,
        opponent_cards_in_hand=3,
        game_start_time=datetime.now()
    )
    
    game_state = manager.state.live_game_state
    print(f"✅ In game: {game_state.is_in_game}")
    print(f"✅ Turn: {game_state.turn_number}")
    print(f"✅ Life totals: {game_state.player_life} vs {game_state.opponent_life}")
    print(f"✅ Cards: {game_state.player_cards_in_hand} vs {game_state.opponent_cards_in_hand}")
    
    # End game
    manager.update_live_game_state(is_in_game=False)
    print(f"✅ Game ended: {not game_state.is_in_game}")
    
    print()


def test_persistence():
    """Test state persistence and recovery."""
    print("=== Testing State Persistence ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create first manager with temporary config
        manager1 = StateManager()
        
        # Override config to use temp directory
        from src.config.settings import config_manager
        original_config_dir = config_manager.config.directories.config
        config_manager.config.directories.config = str(Path(temp_dir) / "test-config")
        
        # Start session and add game
        starting_rank = Rank(tier=RankTier.GOLD, division=4, pips=1)
        session = manager1.start_session(FormatType.CONSTRUCTED, starting_rank)
        
        game = Game(
            result=GameResult.WIN,
            play_order=PlayOrder.DRAW,
            format_type=FormatType.CONSTRUCTED,
            notes="Test game for persistence"
        )
        manager1.add_game(game)
        
        # Force save
        manager1.enable_auto_save()
        
        print(f"✅ Session created: {session.session_id}")
        print(f"✅ Games in session: {len(session.games)}")
        
        # Create second manager to test loading
        manager2 = StateManager()
        loaded_state = manager2.load_state()
        
        if loaded_state.has_active_session():
            print(f"✅ Loaded active session: {loaded_state.active_session.session_id}")
            print(f"✅ Loaded games: {len(loaded_state.active_session.games)}")
            print(f"✅ Loaded game note: {loaded_state.active_session.games[0].notes}")
        else:
            print("❌ Failed to load active session")
        
        # Restore original config
        config_manager.config.directories.config = original_config_dir
    
    print()


def main():
    """Run all state management tests."""
    print("MTG Arena Tracker - State Management Testing")
    print("=" * 55)
    
    try:
        test_basic_state_operations()
        test_game_tracking()
        test_session_lifecycle()
        test_live_game_state()
        test_persistence()
        
        print("✅ All state management tests completed successfully!")
        
    except Exception as e:
        print(f"❌ State management test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()