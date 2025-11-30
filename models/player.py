"""
Player model for CSS Solaris.
Represents a player in a game.
"""

from typing import Optional


class Player:
    """Represents a player in a CSS Solaris game."""

    def __init__(self, user_id: int, username: str):
        """
        Initialize a player.

        Args:
            user_id: Discord user ID
            username: Discord username
        """
        self.user_id = user_id
        self.username = username
        self.role: Optional[str] = None
        self.is_alive = True
        self.current_vote: Optional[int] = None  # User ID of vote target, or special string

    def vote_for(self, target: int or str):
        """
        Record a vote for a target.

        Args:
            target: User ID of target player, or "VETO"/"ABSTAIN"
        """
        self.current_vote = target

    def clear_vote(self):
        """Clear the current vote."""
        self.current_vote = None

    def eliminate(self):
        """Mark player as eliminated."""
        self.is_alive = False

    def assign_role(self, role: str):
        """
        Assign a role to the player.

        Args:
            role: Name of the role
        """
        self.role = role
