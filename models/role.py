"""
Role models for CSS Solaris.
Defines role classes and their abilities (for future implementation).
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable


class Role(ABC):
    """Base class for all roles."""

    def __init__(self, name: str, team: str):
        """
        Initialize a role.

        Args:
            name: Role name
            team: Team affiliation ("town", "mafia", "neutral")
        """
        self.name = name
        self.team = team
        self.can_vote = True

    @abstractmethod
    def get_description(self) -> str:
        """Get the role description."""
        pass

    def has_night_action(self) -> bool:
        """Check if role has a night action."""
        return False


class Villager(Role):
    """Standard villager role - no special abilities."""

    def __init__(self):
        super().__init__("Villager", "town")

    def get_description(self) -> str:
        return "A regular villager with no special abilities. Win by eliminating all threats to the town."


class Vigilante(Role):
    """Vigilante role - can eliminate one player at night."""

    def __init__(self):
        super().__init__("Vigilante", "town")
        self.shots_remaining = 1  # Can only shoot once per game

    def get_description(self) -> str:
        return "A vigilante who can eliminate one player during the night. Use your shot wisely!"

    def has_night_action(self) -> bool:
        return self.shots_remaining > 0

    def use_shot(self):
        """Use the vigilante's shot."""
        if self.shots_remaining > 0:
            self.shots_remaining -= 1


class Mafia(Role):
    """Mafia role - knows other mafia members, participates in night kills."""

    def __init__(self):
        super().__init__("Mafia", "mafia")

    def get_description(self) -> str:
        return "A member of the mafia. Work with your team to eliminate the town. You know who your teammates are."

    def has_night_action(self) -> bool:
        return True


class Detective(Role):
    """Detective role - can investigate one player per night."""

    def __init__(self):
        super().__init__("Detective", "town")

    def get_description(self) -> str:
        return "A detective who can investigate one player each night to learn their team affiliation."

    def has_night_action(self) -> bool:
        return True


# Role factory for easy role creation
ROLE_CLASSES = {
    "villager": Villager,
    "vigilante": Vigilante,
    "mafia": Mafia,
    "detective": Detective
}


def create_role(role_name: str) -> Optional[Role]:
    """
    Create a role instance by name.

    Args:
        role_name: Name of the role to create

    Returns:
        Role instance or None if role not found
    """
    role_class = ROLE_CLASSES.get(role_name.lower())
    if role_class:
        return role_class()
    return None
