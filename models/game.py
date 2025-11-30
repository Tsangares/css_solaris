"""
Game model for CSS Solaris.
Represents a game instance with all its state.
"""

from typing import Dict, List, Optional
from enum import Enum


class GameStatus(Enum):
    """Possible game states."""
    SIGNUP = "signup"
    ACTIVE = "active"
    ENDED = "ended"


class Game:
    """Represents a CSS Solaris game instance."""

    def __init__(self, name: str, creator_id: int, signup_thread_id: int):
        """
        Initialize a new game.

        Args:
            name: The name of the game
            creator_id: Discord user ID of the game creator
            signup_thread_id: Discord channel ID of the signup thread
        """
        self.name = name
        self.creator_id = creator_id
        self.signup_thread_id = signup_thread_id
        self.status = GameStatus.SIGNUP
        self.current_day = 0
        self.players: List[int] = []  # List of Discord user IDs
        self.channels: Dict[int, Dict[str, int]] = {}  # {day: {votes_channel_id, discussion_channel_id, votes_message_id}}
        self.roles: Dict[int, str] = {}  # {user_id: role_name}
        self.eliminated_players: List[int] = []  # List of eliminated player IDs

    def add_player(self, user_id: int) -> bool:
        """
        Add a player to the game.

        Args:
            user_id: Discord user ID to add

        Returns:
            True if player was added, False if already in game
        """
        if user_id in self.players:
            return False
        self.players.append(user_id)
        return True

    def remove_player(self, user_id: int) -> bool:
        """
        Remove a player from the game.

        Args:
            user_id: Discord user ID to remove

        Returns:
            True if player was removed, False if not in game
        """
        if user_id not in self.players:
            return False
        self.players.remove(user_id)
        return True

    def start_game(self) -> bool:
        """
        Start the game (move from SIGNUP to ACTIVE).

        Returns:
            True if game was started, False if already active/ended
        """
        if self.status != GameStatus.SIGNUP:
            return False
        self.status = GameStatus.ACTIVE
        self.current_day = 1
        return True

    def end_game(self):
        """End the game."""
        self.status = GameStatus.ENDED

    def eliminate_player(self, user_id: int):
        """
        Mark a player as eliminated.

        Args:
            user_id: Discord user ID to eliminate
        """
        if user_id not in self.eliminated_players:
            self.eliminated_players.append(user_id)

    def is_player_alive(self, user_id: int) -> bool:
        """
        Check if a player is still alive in the game.

        Args:
            user_id: Discord user ID to check

        Returns:
            True if player is alive, False otherwise
        """
        return user_id in self.players and user_id not in self.eliminated_players

    def get_alive_players(self) -> List[int]:
        """
        Get list of all alive players.

        Returns:
            List of Discord user IDs of alive players
        """
        return [p for p in self.players if p not in self.eliminated_players]

    def to_dict(self) -> dict:
        """
        Convert game to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the game
        """
        return {
            "name": self.name,
            "creator_id": self.creator_id,
            "signup_thread_id": self.signup_thread_id,
            "status": self.status.value,
            "current_day": self.current_day,
            "players": self.players,
            "channels": self.channels,
            "roles": self.roles,
            "eliminated_players": self.eliminated_players
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Game':
        """
        Create a Game instance from a dictionary.

        Args:
            data: Dictionary containing game data

        Returns:
            Game instance
        """
        game = cls(
            name=data["name"],
            creator_id=data["creator_id"],
            signup_thread_id=data["signup_thread_id"]
        )
        game.status = GameStatus(data["status"])
        game.current_day = data["current_day"]
        game.players = data["players"]
        game.channels = {int(k): v for k, v in data["channels"].items()}  # Convert string keys back to int
        game.roles = {int(k): v for k, v in data["roles"].items()}
        game.eliminated_players = data.get("eliminated_players", [])
        return game
