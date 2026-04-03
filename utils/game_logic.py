"""
Game logic utilities for CSS Solaris.
Contains pure functions for vote counting and game state transitions.
"""

import random
from typing import Dict, Tuple, Optional, List


def count_votes(votes: Dict[int, int or str], alive_players: List[int]) -> Tuple[Optional[int], str, Dict]:
    """
    Count votes and determine elimination.

    Args:
        votes: Dictionary mapping voter_id to target_id or "ABSTAIN"
        alive_players: List of alive player IDs

    Returns:
        Tuple of (eliminated_player_id, result_type, vote_tally)
    """
    tally = {}
    abstain_count = 0

    # Count only votes from alive players
    for voter_id, target in votes.items():
        if voter_id not in alive_players:
            continue
        if target == "ABSTAIN":
            abstain_count += 1
        else:
            tally[target] = tally.get(target, 0) + 1

    # Check if no one voted
    if not tally and abstain_count == 0:
        return None, "no_votes", {}

    # Check if majority abstained
    total_votes = sum(1 for v in votes if v in alive_players)
    if abstain_count > total_votes / 2:
        return None, "majority_abstain", tally

    # Find player(s) with most votes
    if tally:
        max_votes = max(tally.values())
        tied_players = [player_id for player_id, vote_count in tally.items() if vote_count == max_votes]

        if len(tied_players) > 1:
            return None, "tie", tally

        eliminated = tied_players[0]
        return eliminated, "elimination", tally

    # Only abstain votes, no elimination
    return None, "majority_abstain", tally


def format_vote_message(votes: Dict[int, int or str], user_names: Dict[int, str],
                        alive_players: List[int] = None) -> str:
    """
    Format a vote tracking message.

    Args:
        votes: Dictionary mapping voter_id to target_id or "ABSTAIN"
        user_names: Dictionary mapping user_id to username
        alive_players: List of alive player IDs (to show who hasn't voted)

    Returns:
        Formatted message string
    """
    tally = {}
    abstain_voters = []
    voters_list = []

    for voter_id, target in votes.items():
        voter_name = user_names.get(voter_id, f"User {voter_id}")
        if target == "ABSTAIN":
            abstain_voters.append(voter_name)
        else:
            target_name = user_names.get(target, f"User {target}")
            voters_list.append(f"{voter_name} → {target_name}")
            tally[target] = tally.get(target, 0) + 1

    lines = []

    if not votes:
        lines.append("*No votes cast yet.*")
    else:
        # Tally section - most important, goes first
        lines.append("**Tally**")
        bar_max = max(tally.values()) if tally else 1
        for target_id, count in sorted(tally.items(), key=lambda x: x[1], reverse=True):
            target_name = user_names.get(target_id, f"User {target_id}")
            bar = "█" * count + "░" * (bar_max - count)
            lines.append(f"`{bar}` **{count}** — {target_name}")
        if abstain_voters:
            lines.append(f"`{'░' * bar_max}` **{len(abstain_voters)}** — Abstain")

        # Individual votes
        lines.append("")
        lines.append("**Votes Cast**")
        for vote_line in voters_list:
            lines.append(f"› {vote_line}")
        if abstain_voters:
            for name in abstain_voters:
                lines.append(f"› {name} → Abstain")

    # Status line
    lines.append("")
    if alive_players:
        voted_count = sum(1 for pid in alive_players if pid in votes)
        total = len(alive_players)
        if voted_count == total:
            lines.append(f"✅ All **{total}** players have voted")
        else:
            not_voted = [pid for pid in alive_players if pid not in votes]
            not_voted_names = [user_names.get(pid, f"User {pid}") for pid in not_voted]
            lines.append(f"⏳ **{voted_count}/{total}** voted — waiting on {', '.join(not_voted_names)}")

    return "\n".join(lines)


def format_day_end_message(eliminated_id: Optional[int], result_type: str,
                           tally: Dict, user_names: Dict[int, str], day: int,
                           roles: Dict[int, str] = None, reveal_role: bool = False) -> str:
    """Format the end-of-day announcement message. Role is hidden by default (revealed next day)."""
    from utils import roles as role_utils

    lines = []

    if result_type == "elimination":
        eliminated_name = user_names.get(eliminated_id, f"User {eliminated_id}")
        votes = tally.get(eliminated_id, 0)

        if reveal_role and roles and eliminated_id in roles:
            eliminated_role = roles.get(eliminated_id)
            role_info = role_utils.get_role_info(eliminated_role)
            role_emoji = role_info.get('emoji', '')
            lines.append(
                f"**{eliminated_name}** was eliminated with **{votes}** vote{'s' if votes != 1 else ''}.\n"
                f"They were: {role_emoji} **{eliminated_role}**"
            )
        else:
            lines.append(f"**{eliminated_name}** was eliminated with **{votes}** vote{'s' if votes != 1 else ''}.\nTheir role will be revealed at dawn...")

    elif result_type == "tie":
        tied_names = [user_names.get(pid, f"User {pid}") for pid in tally.keys()]
        lines.append(f"The vote ended in a **tie** between {', '.join(tied_names)}.")
        lines.append("No one was eliminated.")

    elif result_type == "no_votes":
        lines.append("No votes were cast. No one was eliminated.")

    elif result_type == "majority_abstain":
        lines.append("The majority abstained. No one was eliminated.")

    return "\n".join(lines)


def check_win_condition(alive_players: List[int], roles: Dict[int, str],
                        settings: Dict = None) -> Optional[str]:
    """Check if any team has won the game."""
    if len(alive_players) == 0:
        return "crew"

    if not roles:
        if len(alive_players) <= 1:
            return "game_over"
        return None

    settings = settings or {}
    win_crew = settings.get("win_crew", "all_saboteurs_dead")
    win_saboteur = settings.get("win_saboteur", "half_or_more")

    alive_crew = 0
    alive_saboteurs = 0

    for player_id in alive_players:
        role = roles.get(player_id, "Crew Member")
        if role == "Saboteur":
            alive_saboteurs += 1
        else:
            alive_crew += 1

    # Crew win conditions
    if win_crew == "all_saboteurs_dead" and alive_saboteurs == 0:
        return "crew"
    elif win_crew == "majority_crew" and alive_crew > alive_saboteurs * 2:
        return "crew"

    # Saboteur win conditions
    if win_saboteur == "half_or_more" and alive_saboteurs >= len(alive_players) / 2:
        return "saboteur"
    elif win_saboteur == "majority" and alive_saboteurs > alive_crew:
        return "saboteur"
    elif win_saboteur == "last_standing" and alive_crew == 0:
        return "saboteur"

    return None


def resolve_night_kill(night_kill_votes: Dict[int, int]) -> Optional[int]:
    """
    Resolve saboteur kill votes. Majority wins; random on tie.

    Args:
        night_kill_votes: {saboteur_id: target_id}

    Returns:
        Target player ID to kill, or None if no votes
    """
    if not night_kill_votes:
        return None

    # Count votes per target
    tally = {}
    for target in night_kill_votes.values():
        tally[target] = tally.get(target, 0) + 1

    max_votes = max(tally.values())
    top_targets = [t for t, c in tally.items() if c == max_votes]

    # Random pick on tie
    return random.choice(top_targets)
