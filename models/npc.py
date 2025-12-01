"""
NPC model for CSS Solaris.
Represents bot-controlled players for testing.
"""

from typing import Optional


class NPC:
    """Represents a bot-controlled player for testing."""

    # NPC IDs are negative to distinguish from real Discord user IDs
    _next_id = -1

    def __init__(self, name: str, profile: Optional[str] = None, npc_id: Optional[int] = None):
        """
        Initialize a new NPC.

        Args:
            name: The display name of the NPC
            profile: Optional character profile/description
            npc_id: Optional specific ID (used when loading from database)
        """
        self.name = name
        self.profile = profile or f"An NPC player named {name}"

        if npc_id is not None:
            self.id = npc_id
        else:
            self.id = NPC._next_id
            NPC._next_id -= 1

    def to_dict(self) -> dict:
        """
        Convert NPC to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the NPC
        """
        return {
            "id": self.id,
            "name": self.name,
            "profile": self.profile
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NPC':
        """
        Create an NPC instance from a dictionary.

        Args:
            data: Dictionary containing NPC data

        Returns:
            NPC instance
        """
        npc = cls(
            name=data["name"],
            profile=data["profile"],
            npc_id=data["id"]
        )
        # Update the next_id counter if necessary
        if npc.id <= cls._next_id:
            cls._next_id = npc.id - 1
        return npc

    def __str__(self):
        """String representation of the NPC."""
        return f"NPC({self.name}, ID: {self.id})"
