#!/usr/bin/env python3
"""
Simple configuration tool for MTGA log file path.
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.config.settings import config_manager
except ImportError as e:
    print(f"❌ Error importing config system: {e}")
    print("Make sure you have pydantic installed: pip install pydantic")
    sys.exit(1)


def show_current_config():
    """Display current configuration."""
    config = config_manager.config
    
    print("📋 Current MTGA Configuration:")
    print(f"  Log file path: {config.mtga.log_file_path or 'Not set'}")
    print(f"  Auto-detect: {config.mtga.auto_detect_logs}")
    print(f"  Watch logs: {config.mtga.watch_logs}")
    
    # Show auto-detected paths
    common_paths = config_manager.get_mtga_log_paths()
    if common_paths:
        print(f"\n🔍 Auto-detected paths:")
        for i, path in enumerate(common_paths, 1):
            exists = "✅" if Path(path).exists() else "❌"
            print(f"  {i}. {exists} {path}")
    else:
        print("\n🔍 No common MTGA log paths found")


def set_log_path():
    """Set MTGA log file path."""
    print("\n📁 Set MTGA Log File Path")
    print("-" * 40)
    
    # Show current path
    current_path = config_manager.config.mtga.log_file_path
    if current_path:
        print(f"Current path: {current_path}")
    
    # Get new path from user
    new_path = input("Enter new log file path (or press Enter to skip): ").strip()
    
    if not new_path:
        print("No change made")
        return
    
    # Validate path
    log_file = Path(new_path)
    if not log_file.exists():
        print(f"⚠️  Warning: File does not exist: {log_file}")
        continue_anyway = input("Continue anyway? [y/N]: ").strip().lower()
        if continue_anyway not in ['y', 'yes']:
            print("Cancelled")
            return
    
    # Update configuration
    try:
        config_manager.update(**{"mtga.log_file_path": str(log_file)})
        print(f"✅ Log file path updated: {log_file}")
    except Exception as e:
        print(f"❌ Error updating config: {e}")


def auto_detect_path():
    """Try to auto-detect and set log path."""
    print("\n🔍 Auto-detecting MTGA log path...")
    
    common_paths = config_manager.get_mtga_log_paths()
    if not common_paths:
        print("❌ No MTGA log files found in common locations")
        return
    
    print(f"Found {len(common_paths)} potential log files:")
    for i, path in enumerate(common_paths, 1):
        size_mb = Path(path).stat().st_size / (1024 * 1024)
        print(f"  {i}. {path} ({size_mb:.1f} MB)")
    
    choice = input(f"\nSelect log file [1-{len(common_paths)}] or Enter to cancel: ").strip()
    
    try:
        index = int(choice) - 1
        if 0 <= index < len(common_paths):
            selected_path = common_paths[index]
            config_manager.update(**{"mtga.log_file_path": selected_path})
            print(f"✅ Log file path set to: {selected_path}")
        else:
            print("❌ Invalid selection")
    except (ValueError, IndexError):
        print("Cancelled")


def main():
    """Main configuration interface."""
    print("⚙️  MTGA Tracker Configuration")
    print("=" * 40)
    
    while True:
        show_current_config()
        
        print("\nOptions:")
        print("1. Set log file path manually")
        print("2. Auto-detect log file path")  
        print("3. Test current configuration")
        print("4. Exit")
        
        choice = input("\nEnter choice [1-4]: ").strip()
        
        if choice == '1':
            set_log_path()
        elif choice == '2':
            auto_detect_path()
        elif choice == '3':
            test_configuration()
        elif choice == '4':
            break
        else:
            print("Invalid choice")
        
        print()


def test_configuration():
    """Test current configuration."""
    print("\n🧪 Testing Configuration...")
    
    config = config_manager.config
    
    if not config.mtga.log_file_path:
        print("❌ No log file path configured")
        return
    
    log_file = Path(config.mtga.log_file_path)
    
    if not log_file.exists():
        print(f"❌ Log file does not exist: {log_file}")
        return
    
    try:
        # Try to read a few lines
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(5)]
        
        print(f"✅ Log file is readable: {log_file}")
        print(f"✅ File size: {log_file.stat().st_size / (1024 * 1024):.1f} MB")
        print(f"✅ Sample lines: {len([l for l in lines if l.strip()])} non-empty lines")
        
        # Look for JSON content
        json_lines = [l for l in lines if l.strip().startswith('{')]
        if json_lines:
            print(f"✅ Contains JSON data: {len(json_lines)} JSON lines in sample")
        else:
            print("⚠️  No JSON data found in sample (might be older log format)")
        
    except Exception as e:
        print(f"❌ Error reading log file: {e}")


if __name__ == "__main__":
    main()