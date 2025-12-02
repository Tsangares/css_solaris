"""
Role system for CSS Solaris.
Defines roles, teams, and role assignment logic for Crew vs Saboteurs gameplay.
"""

from typing import Dict, List
import random


# Role definitions
ROLES = {
    "Crew Member": {
        "team": "crew",
        "description": "A loyal crew member. Work with others to find the saboteurs!",
        "emoji": "👨‍🚀",
        "color": "blue"
    },
    "Saboteur": {
        "team": "saboteur",
        "description": "An imposter trying to sabotage the mission. Coordinate with fellow saboteurs!",
        "emoji": "🔪",
        "color": "red"
    },
    "Security Officer": {
        "team": "crew",
        "description": "A crew member with security training. Can investigate one player per night (coming soon).",
        "emoji": "🔍",
        "color": "blue",
        "special": "investigate"
    },
    "Engineer": {
        "team": "crew",
        "description": "A crew member who maintains ship systems. Can protect one player per night (coming soon).",
        "emoji": "🛡️",
        "color": "blue",
        "special": "protect"
    }
}


def get_role_distribution(num_players: int) -> Dict[str, int]:
    """
    Calculate how many of each role for a given player count.

    Rules:
    - 25% saboteurs (rounded up, minimum 1)
    - 1 Security Officer if 6+ players
    - 1 Engineer if 8+ players
    - Rest are Crew Members

    Args:
        num_players: Total number of players

    Returns:
        Dictionary mapping role name to count
    """
    if num_players < 3:
        raise ValueError("Need at least 3 players to start a game")

    distribution = {}

    # Calculate saboteurs (~25%, rounded up, minimum 1)
    num_saboteurs = max(1, (num_players + 3) // 4)  # Rounds up
    distribution["Saboteur"] = num_saboteurs

    # Assign special roles
    if num_players >= 6:
        distribution["Security Officer"] = 1
    else:
        distribution["Security Officer"] = 0

    if num_players >= 8:
        distribution["Engineer"] = 1
    else:
        distribution["Engineer"] = 0

    # Rest are crew members
    special_count = distribution["Security Officer"] + distribution["Engineer"] + num_saboteurs
    distribution["Crew Member"] = num_players - special_count

    return distribution


def assign_roles(player_ids: List[int]) -> Dict[int, str]:
    """
    Assign roles to players randomly based on game size.

    Args:
        player_ids: List of player IDs to assign roles to

    Returns:
        Dictionary mapping player_id to role_name
    """
    num_players = len(player_ids)
    distribution = get_role_distribution(num_players)

    # Create a list of roles to assign
    role_list = []
    for role_name, count in distribution.items():
        role_list.extend([role_name] * count)

    # Shuffle for random assignment
    random.shuffle(role_list)

    # Assign to players
    assignments = {}
    for player_id, role_name in zip(player_ids, role_list):
        assignments[player_id] = role_name

    return assignments


def get_role_info(role_name: str) -> Dict:
    """
    Get information about a specific role.

    Args:
        role_name: Name of the role

    Returns:
        Dictionary with role info, or default Crew Member if not found
    """
    return ROLES.get(role_name, ROLES["Crew Member"])


def get_team(role_name: str) -> str:
    """
    Get the team for a given role.

    Args:
        role_name: Name of the role

    Returns:
        "crew" or "saboteur"
    """
    role_info = get_role_info(role_name)
    return role_info.get("team", "crew")


def format_role_distribution(num_players: int) -> str:
    """
    Format role distribution as a readable string.

    Args:
        num_players: Number of players in the game

    Returns:
        Formatted string showing role distribution
    """
    distribution = get_role_distribution(num_players)
    lines = [f"📊 **Role Distribution ({num_players} players):**\n"]

    # Order: Crew Member, Saboteur, Security Officer, Engineer
    role_order = ["Crew Member", "Saboteur", "Security Officer", "Engineer"]

    for role_name in role_order:
        count = distribution.get(role_name, 0)
        if count > 0:
            role_info = ROLES[role_name]
            emoji = role_info["emoji"]
            lines.append(f"- {emoji} **{role_name}**: {count}")

    return "\n".join(lines)
