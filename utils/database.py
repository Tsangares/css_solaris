"""
Database utilities for CSS Solaris.
Handles reading and writing game state to JSON file.
"""

import json
import os
from typing import Dict, Optional
from models.game import Game


DATABASE_PATH = "data/games.json"


def load_games() -> Dict[str, Game]:
    """
    Load all games from the database file.

    Returns:
        Dictionary mapping game names to Game objects
    """
    if not os.path.exists(DATABASE_PATH):
        return {}

    try:
        with open(DATABASE_PATH, 'r') as f:
            data = json.load(f)
            return {name: Game.from_dict(game_data) for name, game_data in data.items()}
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_games(games: Dict[str, Game]):
    """
    Save all games to the database file.

    Args:
        games: Dictionary mapping game names to Game objects
    """
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    data = {name: game.to_dict() for name, game in games.items()}

    with open(DATABASE_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def get_game(game_name: str) -> Optional[Game]:
    """
    Get a specific game by name.

    Args:
        game_name: Name of the game to retrieve

    Returns:
        Game object or None if not found
    """
    games = load_games()
    return games.get(game_name)


def save_game(game: Game):
    """
    Save or update a single game.

    Args:
        game: Game object to save
    """
    games = load_games()
    games[game.name] = game
    save_games(games)


def delete_game(game_name: str) -> bool:
    """
    Delete a game from the database.

    Args:
        game_name: Name of the game to delete

    Returns:
        True if game was deleted, False if not found
    """
    games = load_games()
    if game_name in games:
        del games[game_name]
        save_games(games)
        return True
    return False


def game_exists(game_name: str) -> bool:
    """
    Check if a game exists in the database.

    Args:
        game_name: Name of the game to check

    Returns:
        True if game exists, False otherwise
    """
    games = load_games()
    return game_name in games
