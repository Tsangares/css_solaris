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
        self.team_channels: Dict[str, int] = {}  # {"saboteurs": channel_id, "dead": channel_id}
        self.discord_roles: Dict[str, int] = {}  # {"crew": role_id, "saboteur": role_id, "dead": role_id}
        self.votes: Dict[int, Dict[int, object]] = {}  # {day: {voter_id: target_id_or_string}}
        self.moderators: List[int] = []  # User IDs with mod access to this game
        self.phase: str = "day"  # "day" or "night"
        self.night_kill_votes: Dict[int, int] = {}  # {saboteur_id: target_id} for current night
        self.last_vote_eliminated: Optional[int] = None  # player eliminated by vote (role revealed at dawn)
        self.day_started_at: Optional[str] = None  # ISO timestamp for day timer
        self.night_started_at: Optional[str] = None  # ISO timestamp for night timer
        self.settings: Dict[str, object] = {
            "player_say_enabled": False,
            "win_crew": "all_saboteurs_dead",       # "all_saboteurs_dead" or "majority_crew"
            "win_saboteur": "half_or_more",          # "half_or_more", "majority", or "last_standing"
            "saboteur_ratio": 0.33,                  # fraction of players assigned as saboteurs
            "day_duration_hours": 24,
        }

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

    def get_player_team(self, user_id: int) -> str:
        """
        Get the team for a given player.

        Args:
            user_id: Discord user ID

        Returns:
            "crew" or "saboteur"
        """
        from utils import roles
        role_name = self.roles.get(user_id, "Crew Member")
        return roles.get_team(role_name)

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
            "eliminated_players": self.eliminated_players,
            "team_channels": self.team_channels,
            "discord_roles": self.discord_roles,
            "votes": {str(day): {str(voter): target for voter, target in day_votes.items()} for day, day_votes in self.votes.items()},
            "moderators": self.moderators,
            "phase": self.phase,
            "night_kill_votes": {str(k): v for k, v in self.night_kill_votes.items()},
            "last_vote_eliminated": self.last_vote_eliminated,
            "day_started_at": self.day_started_at,
            "night_started_at": self.night_started_at,
            "settings": self.settings
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
        game.roles = {int(k): v for k, v in data.get("roles", {}).items()} if data.get("roles") else {}
        game.eliminated_players = data.get("eliminated_players", [])
        game.team_channels = data.get("team_channels", {})
        game.discord_roles = data.get("discord_roles", {})
        # Restore votes: convert string keys back to ints
        raw_votes = data.get("votes", {})
        game.votes = {}
        for day_str, day_votes in raw_votes.items():
            day_int = int(day_str)
            game.votes[day_int] = {}
            for voter_str, target in day_votes.items():
                game.votes[day_int][int(voter_str)] = target
        game.moderators = data.get("moderators", [])
        game.phase = data.get("phase", "day")
        game.night_kill_votes = {int(k): v for k, v in data.get("night_kill_votes", {}).items()}
        game.last_vote_eliminated = data.get("last_vote_eliminated")
        game.day_started_at = data.get("day_started_at")
        game.night_started_at = data.get("night_started_at")
        # Merge saved settings with defaults (so new settings get their defaults)
        saved_settings = data.get("settings", {})
        game.settings.update(saved_settings)
        return game
