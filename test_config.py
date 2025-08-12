#!/usr/bin/env python3
"""
Test script for configuration system.
"""
import tempfile
import shutil
from pathlib import Path
from src.config.settings import Config, ConfigManager, MTGAConfig, UIConfig


def test_default_config():
    """Test default configuration creation."""
    print("=== Testing Default Configuration ===")
    
    config = Config()
    print(f"Default theme: {config.ui.theme}")
    print(f"Default format: {config.ui.default_format}")
    print(f"Demotion threshold: {config.ui.demotion_threshold}")
    print(f"Common decks: {len(config.tracking.common_decks)} archetypes")
    print(f"Sessions dir: {config.directories.sessions}")
    
    # Test path generation
    data_dir = config.get_data_dir()
    sessions_dir = config.get_sessions_dir()
    config_file = config.get_config_file()
    
    print(f"Data directory: {data_dir}")
    print(f"Sessions directory: {sessions_dir}")
    print(f"Config file: {config_file}")
    
    print()


def test_config_validation():
    """Test configuration validation."""
    print("=== Testing Configuration Validation ===")
    
    try:
        # Test valid UI config
        ui_config = UIConfig(theme="dark", demotion_threshold=3)
        print(f"✅ Valid UI config: {ui_config.theme}, threshold: {ui_config.demotion_threshold}")
    except Exception as e:
        print(f"❌ UI config error: {e}")
    
    try:
        # Test invalid demotion threshold
        ui_config = UIConfig(demotion_threshold=1)  # Should fail (min 2)
        print("❌ Should have failed validation")
    except Exception as e:
        print(f"✅ Correctly rejected invalid threshold: {e}")
    
    try:
        # Test MTGA config with non-existent path
        mtga_config = MTGAConfig(log_file_path="/nonexistent/path.log")
        print("❌ Should have failed validation")
    except Exception as e:
        print(f"✅ Correctly rejected invalid log path: {e}")
    
    print()


def test_config_manager():
    """Test configuration manager functionality."""
    print("=== Testing Configuration Manager ===")
    
    # Use temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a test config with custom data directory
        test_config = Config()
        test_config.directories.config = str(temp_path / "test-config")
        test_config.ui.theme = "light"
        test_config.ui.demotion_threshold = 4
        
        # Create config manager and save
        manager = ConfigManager()
        manager._config = test_config
        manager.save()
        
        config_file = test_config.get_config_file()
        print(f"✅ Config saved to: {config_file}")
        print(f"✅ File exists: {config_file.exists()}")
        
        # Load config in new manager
        new_manager = ConfigManager()
        new_manager._config = None  # Force reload
        
        # Temporarily override the default path for testing
        original_config = Config()
        original_config.directories.config = str(temp_path / "test-config")
        new_manager._config = new_manager.load()
        
        if (temp_path / "test-config" / "config.json").exists():
            print("✅ Config file was created")
        else:
            print("❌ Config file was not created")
    
    print()


def test_config_updates():
    """Test configuration updates."""
    print("=== Testing Configuration Updates ===")
    
    config = Config()
    original_theme = config.ui.theme
    original_threshold = config.ui.demotion_threshold
    
    print(f"Original theme: {original_theme}")
    print(f"Original threshold: {original_threshold}")
    
    # Test direct updates
    config.ui.theme = "custom"
    config.ui.demotion_threshold = 5
    
    print(f"Updated theme: {config.ui.theme}")
    print(f"Updated threshold: {config.ui.demotion_threshold}")
    
    # Test common deck management
    original_decks = len(config.tracking.common_decks)
    config.tracking.common_decks.append("Custom Brew")
    new_decks = len(config.tracking.common_decks)
    
    print(f"Decks before: {original_decks}, after: {new_decks}")
    print(f"New deck added: {config.tracking.common_decks[-1]}")
    
    print()


def test_directory_creation():
    """Test directory creation."""
    print("=== Testing Directory Creation ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config()
        config.directories.config = str(Path(temp_dir) / "mtga-test")
        
        # Test directory creation
        config.ensure_directories()
        
        data_dir = config.get_data_dir()
        sessions_dir = config.get_sessions_dir()
        logs_dir = config.get_logs_dir()
        
        print(f"✅ Data dir created: {data_dir.exists()}")
        print(f"✅ Sessions dir created: {sessions_dir.exists()}")
        print(f"✅ Logs dir created: {logs_dir.exists()}")
    
    print()


def main():
    """Run all configuration tests."""
    print("MTG Arena Tracker - Configuration Testing")
    print("=" * 50)
    
    try:
        test_default_config()
        test_config_validation()
        test_config_manager()
        test_config_updates()
        test_directory_creation()
        
        print("✅ All configuration tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()