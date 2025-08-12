#!/usr/bin/env python3
"""
Test script for data persistence layer.
"""
import tempfile
from pathlib import Path
from datetime import datetime, date, timedelta

from src.core.data_manager import DataManager
from src.models.session import Session, SessionStatus
from src.models.game import Game, GameResult, PlayOrder
from src.models.rank import Rank, RankTier, FormatType


def create_test_session(session_id: str, format_type: FormatType, days_ago: int = 0) -> Session:
    """Create a test session with sample data."""
    start_time = datetime.now() - timedelta(days=days_ago)
    
    starting_rank = Rank(tier=RankTier.GOLD, division=3, pips=2)
    session = Session(
        session_id=session_id,
        start_time=start_time,
        format_type=format_type,
        starting_rank=starting_rank,
        current_rank=starting_rank.copy(),
        status=SessionStatus.ENDED
    )
    
    # Add some test games
    games = [
        Game(
            timestamp=start_time + timedelta(minutes=5),
            result=GameResult.WIN,
            play_order=PlayOrder.PLAY,
            format_type=format_type,
            player_deck="Esper Control",
            opponent_deck="Mono-Red Aggro",
            notes="Good control game",
            pips_gained=2
        ),
        Game(
            timestamp=start_time + timedelta(minutes=25),
            result=GameResult.LOSS,
            play_order=PlayOrder.DRAW,
            format_type=format_type,
            player_deck="Esper Control", 
            opponent_deck="Grixis Midrange",
            notes="Flooded out",
            pips_gained=-1
        ),
        Game(
            timestamp=start_time + timedelta(minutes=45),
            result=GameResult.WIN,
            play_order=PlayOrder.PLAY,
            format_type=format_type,
            player_deck="Esper Control",
            opponent_deck="Domain Ramp",
            notes="Close game",
            pips_gained=1
        )
    ]
    
    for game in games:
        session.add_game(game)
    
    session.end_session()
    return session


def test_session_save_load():
    """Test saving and loading sessions."""
    print("=== Testing Session Save/Load ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create data manager with temp directory
        manager = DataManager()
        manager.sessions_dir = Path(temp_dir) / "sessions"
        
        # Create and save test session
        session = create_test_session("test_001", FormatType.CONSTRUCTED)
        saved_path = manager.save_session(session)
        
        print(f"✅ Session saved to: {saved_path.name}")
        print(f"✅ File exists: {saved_path.exists()}")
        
        # Load session back
        loaded_session = manager.load_session(saved_path)
        
        if loaded_session:
            print(f"✅ Session loaded: {loaded_session.session_id}")
            print(f"✅ Games loaded: {len(loaded_session.games)}")
            print(f"✅ Stats: {loaded_session.stats.wins}W-{loaded_session.stats.losses}L")
            print(f"✅ Format: {loaded_session.format_type.value}")
        else:
            print("❌ Failed to load session")
    
    print()


def test_session_listing_filtering():
    """Test listing and filtering sessions."""
    print("=== Testing Session Listing & Filtering ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = DataManager()
        manager.sessions_dir = Path(temp_dir) / "sessions"
        
        # Create multiple test sessions
        sessions = [
            create_test_session("constructed_001", FormatType.CONSTRUCTED, 0),
            create_test_session("constructed_002", FormatType.CONSTRUCTED, 1),
            create_test_session("limited_001", FormatType.LIMITED, 1),
            create_test_session("limited_002", FormatType.LIMITED, 2),
        ]
        
        # Save all sessions
        for session in sessions:
            manager.save_session(session)
        
        # Test listing all sessions
        all_sessions = manager.list_sessions()
        print(f"✅ Total sessions: {len(all_sessions)}")
        
        # Test format filtering
        constructed_sessions = manager.list_sessions(format_type=FormatType.CONSTRUCTED)
        limited_sessions = manager.list_sessions(format_type=FormatType.LIMITED)
        
        print(f"✅ Constructed sessions: {len(constructed_sessions)}")
        print(f"✅ Limited sessions: {len(limited_sessions)}")
        
        # Test date filtering
        today = date.today()
        yesterday = today - timedelta(days=1)
        recent_sessions = manager.list_sessions(date_range=(yesterday, today))
        
        print(f"✅ Recent sessions (last 2 days): {len(recent_sessions)}")
    
    print()


def test_session_summaries():
    """Test session summary generation."""
    print("=== Testing Session Summaries ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = DataManager()
        manager.sessions_dir = Path(temp_dir) / "sessions"
        
        # Create and save test session
        session = create_test_session("summary_test", FormatType.CONSTRUCTED)
        saved_path = manager.save_session(session)
        
        # Get session summary
        summary = manager.get_session_summary(saved_path)
        
        if summary:
            print(f"✅ Session ID: {summary['session_id']}")
            print(f"✅ Format: {summary['format_type']}")
            print(f"✅ Games: {summary['game_count']}")
            print(f"✅ Record: {summary['wins']}W-{summary['losses']}L")
            print(f"✅ Status: {summary['status']}")
        else:
            print("❌ Failed to generate summary")
        
        # Test recent sessions
        recent = manager.get_recent_sessions(limit=5)
        print(f"✅ Recent sessions found: {len(recent)}")
    
    print()


def test_statistics_calculation():
    """Test overall statistics calculation."""
    print("=== Testing Statistics Calculation ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = DataManager()
        manager.sessions_dir = Path(temp_dir) / "sessions"
        
        # Create multiple sessions with different formats
        sessions = [
            create_test_session("stats_001", FormatType.CONSTRUCTED, 0),
            create_test_session("stats_002", FormatType.CONSTRUCTED, 1),
            create_test_session("stats_003", FormatType.LIMITED, 1),
        ]
        
        for session in sessions:
            manager.save_session(session)
        
        # Test overall stats
        overall_stats = manager.get_overall_stats()
        print(f"✅ Overall games: {overall_stats.total_games}")
        print(f"✅ Overall win rate: {overall_stats.win_rate():.1f}%")
        print(f"✅ Play/Draw split: {overall_stats.play_games}/{overall_stats.draw_games}")
        
        # Test format-specific stats
        constructed_stats = manager.get_format_stats(FormatType.CONSTRUCTED)
        limited_stats = manager.get_format_stats(FormatType.LIMITED)
        
        print(f"✅ Constructed games: {constructed_stats.total_games}")
        print(f"✅ Limited games: {limited_stats.total_games}")
        
        # Test daily stats
        today = date.today()
        daily_stats = manager.get_daily_stats(today)
        
        print(f"✅ Today's sessions: {daily_stats['sessions']}")
        print(f"✅ Today's duration: {daily_stats['duration_minutes']} minutes")
        print(f"✅ Today's games: {daily_stats['stats'].total_games}")
    
    print()


def test_data_export():
    """Test data export functionality."""
    print("=== Testing Data Export ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = DataManager()
        manager.sessions_dir = Path(temp_dir) / "sessions"
        
        # Create test sessions
        sessions = [
            create_test_session("export_001", FormatType.CONSTRUCTED),
            create_test_session("export_002", FormatType.LIMITED),
        ]
        
        for session in sessions:
            manager.save_session(session)
        
        # Test export
        export_file = Path(temp_dir) / "export" / "sessions_export.json"
        success = manager.export_session_data(export_file)
        
        print(f"✅ Export successful: {success}")
        print(f"✅ Export file exists: {export_file.exists()}")
        
        if export_file.exists():
            file_size = export_file.stat().st_size
            print(f"✅ Export file size: {file_size} bytes")
    
    print()


def test_log_copying():
    """Test parsed log copying functionality."""
    print("=== Testing Log Copying ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = DataManager()
        manager.logs_dir = Path(temp_dir) / "logs"
        
        # Test log copying
        test_log_content = """
[2025-08-10 16:05:00.123] {"type": "Event_GameRoomEnter", "format": "Standard Ranked"}
[2025-08-10 16:05:01.456] {"type": "Event_MatchGameRoomStateChangedEvent", "gameResult": "Won"}
[2025-08-10 16:05:02.789] {"type": "Event_RankUpdated", "pipsGained": 2}
        """.strip()
        
        log_path = manager.copy_parsed_logs(test_log_content, "test_session_001")
        
        if log_path:
            print(f"✅ Log copied to: {log_path.name}")
            print(f"✅ Log file exists: {log_path.exists()}")
            
            # Verify content
            with open(log_path, 'r') as f:
                saved_content = f.read()
            
            if test_log_content in saved_content:
                print("✅ Log content verified")
            else:
                print("❌ Log content mismatch")
        else:
            print("❌ Failed to copy logs")
    
    print()


def main():
    """Run all data persistence tests."""
    print("MTG Arena Tracker - Data Persistence Testing")
    print("=" * 50)
    
    try:
        test_session_save_load()
        test_session_listing_filtering()
        test_session_summaries()
        test_statistics_calculation()
        test_data_export()
        test_log_copying()
        
        print("✅ All data persistence tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Data persistence test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()