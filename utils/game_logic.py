"""
Game logic utilities for CSS Solaris.
Contains pure functions for vote counting and game state transitions.
"""

from typing import Dict, Tuple, Optional, List


def count_votes(votes: Dict[int, int or str], alive_players: List[int]) -> Tuple[Optional[int], str, Dict]:
    """
    Count votes and determine elimination.

    Args:
        votes: Dictionary mapping voter_id to target_id (or "VETO"/"ABSTAIN")
        alive_players: List of alive player IDs

    Returns:
        Tuple of (eliminated_player_id, result_type, vote_tally)
        - eliminated_player_id: User ID of eliminated player, or None
        - result_type: "elimination", "tie", "no_votes", "majority_abstain"
        - vote_tally: Dictionary of vote counts
    """
    tally = {}
    veto_count = 0
    abstain_count = 0

    # Count all votes
    for voter_id, target in votes.items():
        if target == "VETO":
            veto_count += 1
        elif target == "ABSTAIN":
            abstain_count += 1
        else:
            tally[target] = tally.get(target, 0) + 1

    # Check if no one voted (or everyone vetoed)
    if not tally and abstain_count == 0:
        return None, "no_votes", {}

    # Check if majority abstained
    total_votes = len(votes)
    if abstain_count > total_votes / 2:
        return None, "majority_abstain", tally

    # Find player(s) with most votes
    if tally:
        max_votes = max(tally.values())
        tied_players = [player_id for player_id, vote_count in tally.items() if vote_count == max_votes]

        # Check for tie
        if len(tied_players) > 1:
            return None, "tie", tally

        # Single player with most votes
        eliminated = tied_players[0]
        return eliminated, "elimination", tally

    # Only abstain votes, no elimination
    return None, "majority_abstain", tally


def format_vote_message(votes: Dict[int, int or str], user_names: Dict[int, str]) -> str:
    """
    Format a vote tracking message.

    Args:
        votes: Dictionary mapping voter_id to target_id (or "VETO"/"ABSTAIN")
        user_names: Dictionary mapping user_id to username

    Returns:
        Formatted message string
    """
    lines = ["📊 **Current Votes**\n"]

    # Count votes by target
    tally = {}
    veto_voters = []
    abstain_voters = []
    voters_list = []

    for voter_id, target in votes.items():
        voter_name = user_names.get(voter_id, f"User {voter_id}")

        if target == "VETO":
            veto_voters.append(voter_name)
        elif target == "ABSTAIN":
            abstain_voters.append(voter_name)
        else:
            target_name = user_names.get(target, f"User {target}")
            voters_list.append(f"• {voter_name} → {target_name}")
            tally[target] = tally.get(target, 0) + 1

    # Show individual votes
    for vote_line in voters_list:
        lines.append(vote_line)

    if abstain_voters:
        lines.append(f"• {', '.join(abstain_voters)} → **Abstain**")

    if veto_voters:
        lines.append(f"• {', '.join(veto_voters)} → **Veto**")

    # Show tally
    if tally or abstain_voters or veto_voters:
        lines.append("\n**Tally:**")
        for target_id, count in sorted(tally.items(), key=lambda x: x[1], reverse=True):
            target_name = user_names.get(target_id, f"User {target_id}")
            lines.append(f"  {target_name}: {count} vote{'s' if count != 1 else ''}")

        if abstain_voters:
            lines.append(f"  Abstain: {len(abstain_voters)} vote{'s' if len(abstain_voters) != 1 else ''}")

        if veto_voters:
            lines.append(f"  Veto: {len(veto_voters)} vote{'s' if len(veto_voters) != 1 else ''}")

    return "\n".join(lines)


def format_day_end_message(eliminated_id: Optional[int], result_type: str,
                           tally: Dict, user_names: Dict[int, str], day: int,
                           roles: Dict[int, str] = None) -> str:
    """
    Format the end-of-day announcement message.

    Args:
        eliminated_id: User ID of eliminated player, or None
        result_type: Type of result ("elimination", "tie", "no_votes", "majority_abstain")
        tally: Vote tally dictionary
        user_names: Dictionary mapping user_id to username
        day: Current day number
        roles: Optional dictionary mapping user_id to role_name (for role reveals)

    Returns:
        Formatted announcement message
    """
    from utils import roles as role_utils

    lines = [f"🌙 **Day {day} has ended!**\n"]

    if result_type == "elimination":
        eliminated_name = user_names.get(eliminated_id, f"User {eliminated_id}")
        votes = tally.get(eliminated_id, 0)

        # Add role reveal if roles are assigned
        if roles and eliminated_id in roles:
            eliminated_role = roles.get(eliminated_id)
            role_info = role_utils.get_role_info(eliminated_role)
            role_emoji = role_info.get('emoji', '')
            lines.append(
                f"**{eliminated_name}** has been eliminated with **{votes}** vote{'s' if votes != 1 else ''}!\n"
                f"They were: {role_emoji} **{eliminated_role}**"
            )
        else:
            lines.append(f"**{eliminated_name}** has been eliminated with **{votes}** vote{'s' if votes != 1 else ''}!")

    elif result_type == "tie":
        tied_names = [user_names.get(pid, f"User {pid}") for pid in tally.keys()]
        lines.append(f"The vote ended in a **tie** between {', '.join(tied_names)}.")
        lines.append("**No one has been eliminated.**")

    elif result_type == "no_votes":
        lines.append("**No votes were cast.**")
        lines.append("**No one has been eliminated.**")

    elif result_type == "majority_abstain":
        lines.append("The **majority abstained** from voting.")
        lines.append("**No one has been eliminated.**")

    return "\n".join(lines)


def check_win_condition(alive_players: List[int], roles: Dict[int, str]) -> Optional[str]:
    """
    Check if any team has won the game.

    Args:
        alive_players: List of alive player IDs
        roles: Dictionary mapping player_id to role_name

    Returns:
        - "crew": Crew wins (all saboteurs eliminated)
        - "saboteur": Saboteurs win (≥50% of alive players are saboteurs)
        - "game_over": Legacy win condition (1 or 0 players left, no roles)
        - None: Game continues
    """
    if len(alive_players) == 0:
        return "crew"  # Default to crew if everyone dies somehow

    # If no roles assigned yet, use old win condition for backward compatibility
    if not roles:
        if len(alive_players) <= 1:
            return "game_over"
        return None

    # Count alive by team
    alive_crew = 0
    alive_saboteurs = 0

    for player_id in alive_players:
        role = roles.get(player_id, "Crew Member")
        if role == "Saboteur":
            alive_saboteurs += 1
        else:
            alive_crew += 1

    # Crew wins if all saboteurs are eliminated
    if alive_saboteurs == 0:
        return "crew"

    # Saboteurs win if they are ≥50% of alive players
    if alive_saboteurs >= len(alive_players) / 2:
        return "saboteur"

    # Game continues
    return None
