"""
Bot utility functions for CSS Solaris.
"""

import discord


def get_required_permissions() -> discord.Permissions:
    """
    Get the permissions required for the bot to function properly.

    Returns:
        Permissions object with all required permissions
    """
    perms = discord.Permissions()
    perms.manage_roles = True
    perms.manage_channels = True
    perms.manage_threads = True
    perms.create_public_threads = True
    perms.send_messages_in_threads = True
    perms.send_messages = True
    perms.embed_links = True
    perms.attach_files = True
    perms.read_message_history = True
    perms.add_reactions = True
    perms.use_external_emojis = True
    return perms


def generate_invite_link(client_id: int) -> str:
    """
    Generate an invite link for the bot with all required permissions.

    Args:
        client_id: The bot's application/client ID

    Returns:
        OAuth2 invite URL
    """
    permissions = get_required_permissions()

    # Generate OAuth2 URL
    # Scopes: bot (for the bot itself) and applications.commands (for slash commands)
    url = (
        f"https://discord.com/api/oauth2/authorize?"
        f"client_id={client_id}&"
        f"permissions={permissions.value}&"
        f"scope=bot%20applications.commands"
    )

    return url


def check_missing_permissions(bot_permissions: discord.Permissions) -> list[str]:
    """
    Check which required permissions are missing.

    Args:
        bot_permissions: The bot's current permissions in a guild

    Returns:
        List of missing permission names
    """
    required = get_required_permissions()
    missing = []

    permission_names = {
        'manage_roles': 'Manage Roles',
        'manage_channels': 'Manage Channels',
        'manage_threads': 'Manage Threads',
        'create_public_threads': 'Create Public Threads',
        'send_messages_in_threads': 'Send Messages in Threads',
        'send_messages': 'Send Messages',
        'embed_links': 'Embed Links',
        'attach_files': 'Attach Files',
        'read_message_history': 'Read Message History',
        'add_reactions': 'Add Reactions',
        'use_external_emojis': 'Use External Emojis',
    }

    for perm_name, display_name in permission_names.items():
        if getattr(required, perm_name) and not getattr(bot_permissions, perm_name):
            missing.append(display_name)

    return missing
