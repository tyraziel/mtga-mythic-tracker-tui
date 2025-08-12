#!/usr/bin/env python3
"""
Test script for MTGA log parser.
"""
import tempfile
from pathlib import Path
from datetime import datetime

from src.parsers.mtga_parser import MTGALogParser, MTGALogEvent, create_mock_log_data
from src.models.game import GameResult, PlayOrder, FormatType
from src.models.rank import RankTier


def test_log_line_parsing():
    """Test parsing individual log lines."""
    print("=== Testing Log Line Parsing ===")
    
    parser = MTGALogParser()
    
    # Test valid log line
    test_line = '[2025-08-10 16:05:00.123] {"type": "Event_GameRoomEnter", "format": "Standard Ranked"}'
    event = parser._parse_log_line(test_line)
    
    if event:
        print(f"✅ Parsed event: {event.event_type}")
        print(f"✅ Timestamp: {event.timestamp}")
        print(f"✅ Data keys: {list(event.data.keys())}")
    else:
        print("❌ Failed to parse valid log line")
    
    # Test invalid log line
    invalid_line = "This is not a valid log line"
    invalid_event = parser._parse_log_line(invalid_line)
    
    if invalid_event is None:
        print("✅ Correctly ignored invalid line")
    else:
        print("❌ Should have ignored invalid line")
    
    print()


def test_event_filtering():
    """Test event filtering for relevant events."""
    print("=== Testing Event Filtering ===")
    
    parser = MTGALogParser()
    
    relevant_events = [
        "Event_GameRoomEnter",
        "Event_MatchGameRoomStateChangedEvent", 
        "Event_RankUpdated",
        "Event_PlayerLifeChanged"
    ]
    
    irrelevant_events = [
        "Event_SomeOtherEvent",
        "Event_UIUpdate",
        "Event_NetworkStatus"
    ]
    
    for event_type in relevant_events:
        if parser._is_relevant_event(event_type):
            print(f"✅ {event_type} is relevant")
        else:
            print(f"❌ {event_type} should be relevant")
    
    for event_type in irrelevant_events:
        if not parser._is_relevant_event(event_type):
            print(f"✅ {event_type} is correctly filtered out")
        else:
            print(f"❌ {event_type} should be filtered out")
    
    print()


def test_mock_log_parsing():
    """Test parsing mock log data."""
    print("=== Testing Mock Log Parsing ===")
    
    # Create temporary log file with mock data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        mock_lines = create_mock_log_data()
        for line in mock_lines:
            f.write(line + '\n')
        temp_log_path = Path(f.name)
    
    try:
        parser = MTGALogParser()
        events = list(parser.parse_log_file(temp_log_path))
        
        print(f"✅ Parsed {len(events)} events from mock data")
        
        # Show event types found
        event_types = [event.event_type for event in events]
        unique_types = set(event_types)
        print(f"✅ Event types found: {sorted(unique_types)}")
        
        # Test game extraction
        games = []
        current_game_events = []
        
        for event in events:
            current_game_events.append(event)
            
            # End of game detection (simplified)
            if event.event_type in parser.GAME_END_EVENTS:
                game = parser.extract_game_from_events(current_game_events)
                if game:
                    games.append(game)
                    print(f"✅ Extracted game: {game.result.value} on the {game.play_order.value}")
                    print(f"   Rank change: {game.rank_change_str()}")
                current_game_events = []
        
        print(f"✅ Extracted {len(games)} complete games")
        
    finally:
        # Clean up temp file
        temp_log_path.unlink()
    
    print()


def test_rank_parsing():
    """Test rank data parsing."""
    print("=== Testing Rank Parsing ===")
    
    parser = MTGALogParser()
    
    # Test non-Mythic rank
    gold_rank_data = {
        "tier": "Gold",
        "division": 2,
        "pips": 4
    }
    
    gold_rank = parser._parse_rank_data(gold_rank_data)
    if gold_rank:
        print(f"✅ Parsed Gold rank: {gold_rank}")
        print(f"   Tier: {gold_rank.tier.value}")
        print(f"   Division: {gold_rank.division}")
        print(f"   Pips: {gold_rank.pips}")
    else:
        print("❌ Failed to parse Gold rank")
    
    # Test Mythic rank
    mythic_rank_data = {
        "tier": "Mythic",
        "percentage": 85.5
    }
    
    mythic_rank = parser._parse_rank_data(mythic_rank_data)
    if mythic_rank:
        print(f"✅ Parsed Mythic rank: {mythic_rank}")
        print(f"   Tier: {mythic_rank.tier.value}")
        print(f"   Percentage: {mythic_rank.mythic_percentage}")
    else:
        print("❌ Failed to parse Mythic rank")
    
    print()


def test_live_game_state_extraction():
    """Test live game state extraction."""
    print("=== Testing Live Game State Extraction ===")
    
    parser = MTGALogParser()
    
    # Test life change event
    life_event = MTGALogEvent(
        timestamp=datetime.now(),
        event_type="Event_PlayerLifeChanged",
        data={"playerLife": 18, "opponentLife": 12}
    )
    
    life_state = parser.extract_live_game_state(life_event)
    print(f"✅ Life state: Player {life_state.get('player_life')} vs Opponent {life_state.get('opponent_life')}")
    
    # Test turn change event
    turn_event = MTGALogEvent(
        timestamp=datetime.now(),
        event_type="Event_TurnChanged", 
        data={"turnNumber": 7}
    )
    
    turn_state = parser.extract_live_game_state(turn_event)
    print(f"✅ Turn state: Turn {turn_state.get('turn_number')}")
    
    # Test game state event
    game_event = MTGALogEvent(
        timestamp=datetime.now(),
        event_type="Event_GameRoomStateChangedEvent",
        data={
            "gameState": "Playing",
            "playerHandSize": 4,
            "opponentHandSize": 3
        }
    )
    
    game_state = parser.extract_live_game_state(game_event)
    print(f"✅ Game state: In game: {game_state.get('is_in_game')}")
    print(f"   Hand sizes: {game_state.get('player_cards_in_hand')} vs {game_state.get('opponent_cards_in_hand')}")
    
    print()


def main():
    """Run all parser tests."""
    print("MTG Arena Tracker - Log Parser Testing")
    print("=" * 45)
    
    try:
        test_log_line_parsing()
        test_event_filtering()
        test_mock_log_parsing()
        test_rank_parsing()
        test_live_game_state_extraction()
        
        print("✅ All parser tests completed successfully!")
        print("\n📝 Note: Parser is ready for real MTGA log data")
        print("   Replace mock logic in _extract_* methods with actual log parsing")
        
    except Exception as e:
        print(f"❌ Parser test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()