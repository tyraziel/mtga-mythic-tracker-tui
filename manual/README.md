# MTGA Mythic TUI Session Tracker (Manual)

A standalone Terminal User Interface (TUI) for manually tracking MTG Arena ranked sessions with interactive rank progression visualization.

## Features

✅ **Manual Game Entry** - Add wins/losses with simple hotkeys  
✅ **Interactive Rank Visualization** - Click any rank bar to set position  
✅ **Dual Format Support** - Switch between Constructed (6 bars) and Limited (4 bars)  
✅ **Goal Tracking** - Set session goals and track progress  
✅ **Enhanced Statistics** - Win rates, streaks (best/worst), session history  
✅ **Season Countdown** - Live countdown timer to season end  
✅ **Complete Manual Control** - Edit any field inline (ranks, records, times)  
✅ **State Persistence** - Automatic save/load of session data  

## Installation

```bash
cd manual/
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
# Run with default settings
python3 manual_tui.py

# Custom data directory  
python3 manual_tui.py --data-dir ~/my-mtga-data/

# Fresh start (no persistence)
python3 manual_tui.py --no-save

# Show help
python3 manual_tui.py --help
```

## Keyboard Shortcuts

- **W** - Add win to current session
- **L** - Add loss to current session  
- **F** - Switch format (Constructed ↔ Limited)
- **G** - Set session goal rank
- **M** - Toggle mythic progress display
- **C** - Collapse completed rank tiers
- **H** - Hide completed rank tiers
- **R** - Reset current session
- **Tab** - Switch between panels
- **Q** - Quit application

## Manual Editing

Click on any bracketed field to edit:
- **Rank bars** - Set exact rank position
- **Win/Loss records** - Adjust session or season totals
- **Streaks** - Edit best/worst streaks
- **Times** - Adjust session start or season end
- **Goals** - Set target ranks

## Data Storage

By default, data is stored in:
- **Linux/Mac**: `~/.local/share/mtga-manual-tracker/`
- **Windows**: `%APPDATA%/mtga-manual-tracker/`

Files created:
- `tracker_state.json` - Current session and rank data
- `session_history.json` - Historical session data