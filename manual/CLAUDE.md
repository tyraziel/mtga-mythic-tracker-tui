# MTGA Mythic TUI Session Tracker (Manual)

## Project Overview
A completely standalone Terminal User Interface (TUI) application for manually tracking MTG Arena ranked sessions. Unlike the automated log-parsing version, this focuses on **manual game entry** with intuitive controls and comprehensive rank visualization.

## Architecture

### Standalone Design
- **Single file**: `manual_tui.py` - Complete application with no external dependencies  
- **Built-in models**: Rank progression, session tracking, state management
- **Textual framework**: Professional TUI with inline editing capabilities
- **JSON persistence**: Simple file-based state saving

### Key Features Implemented
✅ **Interactive Rank Panel** - Clickable bars with cascading fill/unfill logic  
✅ **Dual Format Support** - Constructed (6 bars) vs Limited (4 bars) per division  
✅ **Manual Game Entry** - W/L hotkeys with automatic stat updates  
✅ **Goal Tracking** - Session goals with progress indicators  
✅ **Enhanced Statistics** - Win rates, current/best/worst streaks  
✅ **Season Management** - Countdown timers, editable dates  
✅ **State Persistence** - Auto-save/load with CLI options  

## TUI Layout

### Complete Interface Design:
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           MTGA Mythic TUI Session Tracker (Manual)                     │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ 🕐 Season: 23d 14h 32m [Dec 31 11:59PM]  📊 CONSTRUCTED  🎯 BARS: 28  📍 Plat 1 (2/6) │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─ Rank Progress [CONSTRUCTED]─────────────┐ ┌─ Session & Season Stats ──────────────────┐ │
│ │ [F] Switch to Limited                    │ │ 🎯 SESSION GOAL: [Plat 3] 4 bars away!   │ │  
│ │ ──────────────────────────────────────── │ │ ────────────────────────────────────────── │ │
│ │ Mythic    [  ][  ][  ] [87.3%]           │ │ 📊 CURRENT SESSION [CONSTRUCTED]          │ │
│ │ Diamond 1 [  ][  ][  ][  ][  ][  ]       │ │ Started:  [2:15 PM]  Duration: 2h 34m    │ │
│ │ Diamond 2 [  ][  ][  ][  ][  ][  ]       │ │ Record:   [15W] - [8L]  65.2%             │ │
│ │ Diamond 3 [  ][  ][  ][  ][  ][  ]       │ │ Streaks:  W7 / L2 (current)              │ │
│ │ Diamond 4 [  ][  ][  ][  ][  ][  ]       │ │ ────────────────────────────────────────── │ │
│ │ Plat 1    [██][██][  ][  ][  ][  ] ←YOU  │ │ 🏆 SEASON TOTAL [CONSTRUCTED]             │ │
│ │ Plat 2    [██][██][██][██][██][██]       │ │ Record:   [245W] - [198L]  55.3%          │ │
│ │ Plat 3    [██][██][██][██][██][██] ←GOAL │ │ Best:     [W12]  Worst: [L5]              │ │
│ │ Plat 4    [██][██][██][██][██][██]       │ │ Started:  [Gold 2 (3/6)]                 │ │
│ │ ──────────────────────────────────────── │ │ ────────────────────────────────────────── │ │
│ │ Gold 1-4  [████████████████████] FULL   │ │ 📈 SESSION HISTORY                        │ │
│ │ Silver    [████████████████████] FULL   │ │ Today:     15W-8L (65.2%) +7 bars        │ │
│ │ Bronze    [████████████████████] FULL   │ │ Yesterday: 12W-5L (70.6%) +4 bars        │ │
│ │ ──────────────────────────────────────── │ │ This Week: 89W-42L (67.9%) +15 bars      │ │
│ │ [Click any bar to set rank position]     │ │ Last Week: 67W-38L (63.8%) +8 bars       │ │
│ │ [C] Collapse [H] Hide completed tiers    │ │ Best Day:  18W-3L (85.7%) +12 bars       │ │
│ │                                          │ │ ────────────────────────────────────────── │ │
│ │                                          │ │ [W] +Win  [L] +Loss  [R] Reset Session   │ │
│ │                                          │ │ [F] Format [G] Goal  [M] Toggle Mythic   │ │
│ └──────────────────────────────────────────┘ └───────────────────────────────────────────┘ │
│ [Tab] Switch Panels  [S]tart Session  [E]nd Session  [Q]uit  [?] Help                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## MTG Arena Rank System

### Tier Progression & Pip System
- **Bronze/Silver**: 2 pips per win, 0 pips lost (can't derank)
- **Gold**: 2 pips per win, 1 pip lost per loss  
- **Platinum**: 1 pip per win, 1 pip lost per loss ⚠️ **The Platinum Wall**
- **Diamond**: 1 pip per win, 1 pip lost per loss ⚠️ **The Diamond Grind**

### Format Differences
- **Constructed**: 6 bars per division (Bronze 4 → Mythic)
- **Limited**: 4 bars per division (Bronze 4 → Mythic)

### Mythic Handling
When Diamond 1 is complete:
```
┌─ Rank Progress ────────────────┐
│ 🏆 MYTHIC ACHIEVED! 🏆          │
│                                │  
│ Current: [87.3%] ←click to edit │
│ Best:    [92.1%] ←click to edit │  
│                                │
│ Or enter rank: [#1247] ←edit   │
│                                │
│ [H] Show Full Rank History     │
└────────────────────────────────┘
```

## Manual Interaction Features

### Clickable Elements (Inline Editing)
All bracketed items `[value]` are click-to-edit:
- **Rank Progress**: Click any bar to set rank with cascading logic
- **Session Stats**: Win/loss records, streaks, start times
- **Season Stats**: Total records, best streaks, season start rank
- **Mythic Values**: Percentage or rank number (#1234)
- **Timing**: Session start time, season end date/time

### Keyboard Controls
- **W/L**: Quick game entry with auto-calculations
- **F**: Format switching (updates bar counts and pip logic)
- **G**: Goal setting with progress tracking
- **C/H**: Rank panel management (collapse/hide completed)
- **M**: Toggle mythic progress display (hideable for sanity!)
- **R**: Session reset with confirmation

### Goal System
- **Session Goals**: "Reach Plat 3 this session" 
- **Progress Tracking**: "4 bars away!" or "2 wins needed!"
- **Visual Indicators**: Goal rank highlighted in progression panel
- **Motivation**: Clear, achievable targets per session

## State Management

### Data Persistence
```json
{
  "current_format": "CONSTRUCTED",
  "constructed_rank": {
    "tier": "Platinum", 
    "division": 1,
    "pips": 2
  },
  "limited_rank": {
    "tier": "Gold",
    "division": 3,
    "pips": 2
  },
  "session": {
    "wins": 15,
    "losses": 8,
    "start_time": "2025-01-15T14:15:00",
    "goal_rank": "Plat 3"
  },
  "season": {
    "wins": 245,
    "losses": 198,
    "end_date": "2025-12-31T23:59:59",
    "best_win_streak": 12,
    "worst_loss_streak": 5
  }
}
```

### CLI Options
```bash
# Default behavior: ~/.local/share/mtga-manual-tracker/
python3 manual_tui.py

# Custom data directory
python3 manual_tui.py --data-dir ~/my-mtga-data/

# No persistence (fresh each run)
python3 manual_tui.py --no-save

# Help and options
python3 manual_tui.py --help
```

## Development Commands

### Running the Application
```bash
# Set up environment
cd manual/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run manual tracker
python3 manual_tui.py

# Run with options
python3 manual_tui.py --data-dir ~/Desktop/mtga-data/ --format Limited
```

### Development Notes
- **Single-file architecture**: All models, UI, and logic in `manual_tui.py`
- **No external dependencies**: Only uses textual framework + Python stdlib
- **Standalone operation**: No imports from parent project's `src/` directory
- **Clean separation**: Models → Widgets → App → CLI argument handling

## Implementation Status

### Design Phase: ✅ **COMPLETE**
✅ **TUI Layout**: Complete mockup with all panels and interactions  
✅ **Feature Requirements**: All manual editing and hotkey functions defined  
✅ **Rank System Logic**: MTG Arena progression rules documented  
✅ **State Persistence**: Data structure and file management planned  

### Implementation Phase: ✅ **COMPLETE**
✅ **Core Models**: Rank, Session, Statistics with manual update logic  
✅ **Textual Widgets**: Interactive panels, top panel layout, confirmation popups  
✅ **Application Logic**: Hotkey handling, format switching, goal tracking  
✅ **CLI Interface**: Argument parsing, data directory options  
✅ **State Management**: JSON save/load with automatic persistence  
✅ **Bug Fixes**: Timer API, widget initialization, panel composition  

### Current Status: 🎯 **PRODUCTION READY APPLICATION**
✅ **manual_tui.py**: Complete 1400+ line standalone application  
✅ **All Core Features**: Win/loss tracking, rank progression, format switching  
✅ **Professional UI**: 4-column top panel, colored rank visualization, stats panels  
✅ **State Persistence**: Automatic save/load with CLI options  
✅ **Error Handling**: Fixed Textual API compatibility and AttributeError issues  
✅ **Manual Rank Setting**: Complete modal interface with dropdowns and validation  
✅ **Tier Floor Protection**: Proper MTG Arena rank system implementation  
✅ **Visual Polish**: Tier-colored bars, mythic highlighting, current position highlighting  

### Latest Session Work (2025-08-12 - Evening)
✅ **Rank Setting Modal (S key)**: Dropdown interface for tier/division/pips with mythic support  
✅ **Mythic Validation**: Percentage (0-100%) and rank number (≥1) validation  
✅ **Tier Floor Protection**: Can't drop from Plat 4→Gold, Diamond 4→Plat, etc.  
✅ **Tier-Colored Bars**: Bronze/Silver/Gold/Platinum(cyan)/Diamond(purple)/Mythic(orange)  
✅ **Current Position Highlighting**: Tier name/division with colored background  
✅ **Mythic Display Integration**: Achievement display above rank bars with proper spacing  
✅ **Auto Collapse/Hide Modes**: Sticky C/H behavior - applies to newly completed tiers  
✅ **Top Panel Mythic Integration**: Shows "🏆 MYTHIC" instead of bars remaining  
✅ **Modal Height & Widget Visibility**: Fixed pips dropdown and modal sizing issues  
✅ **UI Cleanup**: Removed redundant control buttons from right panel - keyboard shortcuts preferred  

### Fully Working Features  
- **W/L Hotkeys**: Add wins/losses with automatic rank progression and tier promotion
- **S Key**: Manual rank setting via modal with tier/division/pips dropdowns
- **F Key**: Switch between Constructed (6 bars) and Limited (4 bars) formats  
- **G Key**: Set session goals with progress tracking
- **M Key**: Toggle mythic achievement display on/off
- **C Key**: Auto-collapse mode for completed tiers (shows colored full bars)
- **H Key**: Auto-hide mode for completed tiers (removes them entirely)
- **R Key**: Reset session with confirmation dialog
- **E Key**: Restart session (same functionality as reset with different confirmation message)
- **State Persistence**: Automatic save to `~/.local/share/mtga-manual-tracker/`
- **CLI Arguments**: `--data-dir`, `--no-save`, `--format` options
- **Visual Highlighting**: Current position highlighted with tier-colored backgrounds
- **Mythic Support**: Percentage and rank number modes with proper validation

### All Tasks Complete ✅
✅ **Manual Rank Setting**: Complete dropdown modal interface with validation  
✅ **Tier-Colored Visualization**: All rank bars show in appropriate tier colors  
✅ **Current Position Highlighting**: Clear visual indication of current rank position  
✅ **Mythic Integration**: Full mythic support with achievement display and orange styling  
✅ **Auto Collapse/Hide**: Intelligent sticky modes for completed tier management  

### Development Notes
- **Single File**: All code in `manual_tui.py` - no external dependencies from main project
- **Textual Version**: Compatible with textual>=0.41.0
- **Error Recovery**: Application handles startup errors gracefully
- **Cross Platform**: Works on Linux/Mac/Windows with proper data directory detection

### Data Storage & Testing
- **Linux/Mac**: `~/.local/share/mtga-manual-tracker/`
- **Windows**: `~/AppData/Roaming/mtga-manual-tracker/`
- **Testing**: Remove data directory to reset state for fresh testing
- **State Includes**: Ranks, session stats, collapsed/hidden tiers, auto-modes

## Project Goals

This manual tracker provides MTG Arena players with:
1. **Complete control** over rank tracking without log file dependencies
2. **Intuitive interaction** through click-to-edit and keyboard shortcuts  
3. **Professional UI/UX** rivaling desktop applications in a terminal
4. **Motivational tools** like goal setting and progress visualization
5. **Standalone operation** - works anywhere Python + Textual are available

Perfect for players who want precise session tracking, goal-oriented climbing, or situations where log parsing isn't available/desired.

## Time Tracking Notes
- **Requirements Phase**: Completed - comprehensive TUI design with all features mapped  
- **Implementation Phase**: Completed - functional standalone application with all core features  
- **Bug Fix Phase**: Completed - resolved Textual API compatibility and widget composition issues  
- **UI Polish Phase**: Completed - improved top panel layout and information organization  
- **Architecture**: Single-file approach achieved for maximum portability and simplicity  

### Latest Session Summary (2025-08-19)  
**Total Implementation Time**: 6h 52min across 7 sessions  
**Lines of Code**: 2,400+ in `manual_tui.py` (now modularized)  
**Features Completed**: Legal compliance framework + About modal + modularization  
**Status**: Production-ready with complete licensing and transparency  

**Key Accomplishments This Session (1h)**:
1. **Complete Licensing Framework** - Added VCL-0.1-Experimental + MIT dual licensing
2. **Legal Compliance** - Wizards Fan Content Policy + AI development transparency  
3. **Professional About Modal** - I key with project info, licensing, GitHub links
4. **Architecture Modularization** - Extracted models/ and storage/ packages
5. **UI Polish** - Season Current display, cleaned modal layout, Ctrl+Q fix
6. **Documentation** - AI_DEVELOPMENT.md + comprehensive attribution standards

**Previous Session Summary (2025-08-13)**:
**Features Completed**: Advanced timer systems + milestone celebrations  
**Key Accomplishments**:
1. **Game Timer System** - Dedicated game timing with Shift+S start, auto-stop on W/L
2. **Session Pause/Resume** - P key pauses both session and game timers with visual indicators
3. **Milestone Toast System** - Celebrations for tier promotions, win milestones, win rate achievements
4. **Dual Time Tracking** - Real time vs active time for comprehensive session analytics
5. **Goal Achievement Toasts** - Celebratory notifications when session goals are reached
6. **Error Resolution** - Fixed datetime serialization, type hints, and variable scope issues

**Next Session Goals**:
- Create automated version based on manual TUI foundation
- Complete UI component extraction to ui/ package
- Implement per-format tracking (separate Limited/Constructed stats)
- Add daily/weekly stats tracking with midnight rollover detection

### Development Context for Future Sessions
The manual tracker is a **complete, functional application** that can be picked up and enhanced in future sessions. The core architecture is solid and all fundamental features work correctly. Future work should focus on UI/UX improvements and enhanced interactivity rather than core functionality.