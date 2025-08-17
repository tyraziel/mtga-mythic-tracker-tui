"""
UI package for MTGA Manual TUI Tracker.

Contains Textual widgets and panels for the user interface.
"""

from .widgets import EditableText, TopPanel, RankProgressPanel, StatsPanel

__all__ = [
    'EditableText',
    'TopPanel', 
    'RankProgressPanel',
    'StatsPanel'
]