"""
Database utilities for CSS Solaris.
Handles reading and writing game state to JSON file.
"""

import json
import os
from typing import Dict, Optional
from models.game import Game
from models.npc import NPC


DATABASE_PATH = "data/games.json"
NPC_DATABASE_PATH = "data/npcs.json"


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


# NPC Database Functions

def load_npcs() -> Dict[str, NPC]:
    """
    Load all NPCs from the database file.

    Returns:
        Dictionary mapping NPC names to NPC objects
    """
    if not os.path.exists(NPC_DATABASE_PATH):
        return {}

    try:
        with open(NPC_DATABASE_PATH, 'r') as f:
            data = json.load(f)
            return {name: NPC.from_dict(npc_data) for name, npc_data in data.items()}
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_npcs(npcs: Dict[str, NPC]):
    """
    Save all NPCs to the database file.

    Args:
        npcs: Dictionary mapping NPC names to NPC objects
    """
    # Ensure data directory exists
    os.makedirs(os.path.dirname(NPC_DATABASE_PATH), exist_ok=True)

    data = {name: npc.to_dict() for name, npc in npcs.items()}

    with open(NPC_DATABASE_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def get_npc(npc_name: str) -> Optional[NPC]:
    """
    Get a specific NPC by name (case-insensitive).

    Args:
        npc_name: Name of the NPC to retrieve

    Returns:
        NPC object or None if not found
    """
    npcs = load_npcs()
    # Case-insensitive search
    for name, npc in npcs.items():
        if name.lower() == npc_name.lower():
            return npc
    return None


def save_npc(npc: NPC):
    """
    Save or update a single NPC.

    Args:
        npc: NPC object to save
    """
    npcs = load_npcs()
    npcs[npc.name] = npc
    save_npcs(npcs)


def delete_npc(npc_name: str) -> bool:
    """
    Delete an NPC from the database (case-insensitive).

    Args:
        npc_name: Name of the NPC to delete

    Returns:
        True if NPC was deleted, False if not found
    """
    npcs = load_npcs()
    # Case-insensitive search
    npc_name_lower = npc_name.lower()
    for name in list(npcs.keys()):
        if name.lower() == npc_name_lower:
            del npcs[name]
            save_npcs(npcs)
            return True
    return False


def npc_exists(npc_name: str) -> bool:
    """
    Check if an NPC exists in the database (case-insensitive).

    Args:
        npc_name: Name of the NPC to check

    Returns:
        True if NPC exists, False otherwise
    """
    npcs = load_npcs()
    # Case-insensitive check
    npc_name_lower = npc_name.lower()
    return any(name.lower() == npc_name_lower for name in npcs.keys())


def get_npc_by_id(npc_id: int) -> Optional[NPC]:
    """
    Get an NPC by their ID.

    Args:
        npc_id: ID of the NPC to retrieve

    Returns:
        NPC object or None if not found
    """
    npcs = load_npcs()
    for npc in npcs.values():
        if npc.id == npc_id:
            return npc
    return None
