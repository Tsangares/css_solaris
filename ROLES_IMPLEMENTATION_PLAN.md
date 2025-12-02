# CSS Solaris - Role System Implementation Plan

## Overview
Transform CSS Solaris into a full social deduction game with **Crew** vs **Saboteurs** (space-themed Mafia).

## Theme: Space Crew vs Saboteurs
- **Crew Team**: Honest players trying to identify and eliminate saboteurs
- **Saboteur Team**: Deceptive players trying to sabotage the mission
- **Role Reveal**: On death, player's role is announced publicly
- **Balance**: ~25% saboteurs (1 in 4 players)

---

## Phase 1: Core Role Infrastructure

### 1.1 Update Data Models
**File**: `models/game.py`

Add to `Game` class:
```python
class Game:
    # Existing fields...
    roles: Dict[int, str]  # player_id -> role_name mapping
    team_channels: Dict[str, int]  # "saboteurs" -> channel_id, "dead" -> channel_id
    discord_roles: Dict[str, int]  # "crew" -> role_id, "saboteur" -> role_id, "dead" -> role_id
```

Add to `Player` class (if exists) or track in Game:
```python
def get_player_team(self, player_id: int) -> str:
    """Return 'crew' or 'saboteur'"""
    role = self.roles.get(player_id)
    if role in ["Saboteur"]:
        return "saboteur"
    return "crew"
```

### 1.2 Role Definitions
**File**: `utils/roles.py` (NEW)

```python
# Role configurations
ROLES = {
    "Crew Member": {
        "team": "crew",
        "description": "A loyal crew member. Work with others to find the saboteurs!",
        "emoji": "👨‍🚀"
    },
    "Saboteur": {
        "team": "saboteur",
        "description": "An imposter trying to sabotage the mission. Coordinate with fellow saboteurs!",
        "emoji": "🔪"
    },
    "Security Officer": {
        "team": "crew",
        "description": "Can investigate one player per day to learn their role.",
        "emoji": "🔍",
        "special": "investigate"
    },
    "Engineer": {
        "team": "crew",
        "description": "Can protect one player per day from elimination.",
        "emoji": "🛡️",
        "special": "protect"
    }
}

def assign_roles(player_ids: List[int]) -> Dict[int, str]:
    """
    Assign roles to players based on game size.

    Rules:
    - 25% saboteurs (rounded up, minimum 1)
    - 1 Security Officer if 6+ players
    - 1 Engineer if 8+ players
    - Rest are Crew Members
    """
    pass

def get_role_distribution(num_players: int) -> Dict[str, int]:
    """Calculate how many of each role for a given player count."""
    pass
```

---

## Phase 2: Win Conditions

### 2.1 Update Win Logic
**File**: `utils/game_logic.py`

Replace `check_win_condition()`:
```python
def check_win_condition(alive_players: List[int], roles: Dict[int, str]) -> Optional[str]:
    """
    Check if any team has won.

    Returns:
    - "crew": Crew wins (all saboteurs eliminated)
    - "saboteur": Saboteurs win (≥50% of alive players are saboteurs)
    - None: Game continues
    """
    # Count alive by team
    alive_crew = 0
    alive_saboteurs = 0

    for player_id in alive_players:
        role = roles.get(player_id, "Crew Member")
        if role == "Saboteur":
            alive_saboteurs += 1
        else:
            alive_crew += 1

    # Saboteurs win if they are ≥50% of alive players
    if alive_saboteurs >= len(alive_players) / 2:
        return "saboteur"

    # Crew wins if all saboteurs are eliminated
    if alive_saboteurs == 0:
        return "crew"

    return None
```

---

## Phase 3: Private Channels & Discord Roles

### 3.1 Channel Creation
**File**: `utils/forum_manager.py`

Add new function:
```python
async def create_private_channels(guild, game_name: str, mod_role, bot_member):
    """
    Create private channels for saboteurs and dead players.

    Returns:
        Tuple[TextChannel, TextChannel]: (saboteur_channel, dead_channel)
    """
    # Saboteur Channel (private, saboteurs only)
    saboteur_overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
        bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }

    saboteur_channel = await guild.create_text_channel(
        name=f"🔴-{game_name}-saboteurs",
        category=None,  # Or find/create "Active Games" category
        topic=f"Private channel for {game_name} saboteurs to coordinate",
        overwrites=saboteur_overwrites
    )

    # Dead Channel (read-only for dead players)
    dead_overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }

    dead_channel = await guild.create_text_channel(
        name=f"💀-{game_name}-afterlife",
        category=None,
        topic=f"Eliminated players from {game_name} can watch here",
        overwrites=dead_overwrites
    )

    return saboteur_channel, dead_channel
```

### 3.2 Discord Role Management
**File**: `utils/role_manager.py` (NEW)

```python
async def create_game_roles(guild, game_name: str):
    """
    Create Discord roles for a game.

    Returns:
        Dict[str, discord.Role]: {"crew": role, "saboteur": role, "dead": role}
    """
    crew_role = await guild.create_role(
        name=f"{game_name} - Crew",
        color=discord.Color.blue(),
        mentionable=False
    )

    saboteur_role = await guild.create_role(
        name=f"{game_name} - Saboteur",
        color=discord.Color.red(),
        mentionable=False
    )

    dead_role = await guild.create_role(
        name=f"{game_name} - Dead",
        color=discord.Color.dark_gray(),
        mentionable=False
    )

    return {
        "crew": crew_role.id,
        "saboteur": saboteur_role.id,
        "dead": dead_role.id
    }

async def assign_player_role(guild, member, role_id: int):
    """Add a Discord role to a member."""
    role = guild.get_role(role_id)
    if role:
        await member.add_roles(role)

async def cleanup_game_roles(guild, role_ids: List[int]):
    """Delete game roles when game ends."""
    for role_id in role_ids:
        role = guild.get_role(role_id)
        if role:
            await role.delete()
```

### 3.3 Permission Updates on Death
**File**: `cogs/moderator.py`

In `end_day()` when a player is eliminated:
```python
# Add player to dead role
dead_role_id = game.discord_roles.get("dead")
if dead_role_id and eliminated_id > 0:  # Not an NPC
    try:
        member = await guild.fetch_member(eliminated_id)
        dead_role = guild.get_role(dead_role_id)
        await member.add_roles(dead_role)

        # Remove from their team role
        team = game.get_player_team(eliminated_id)
        team_role_id = game.discord_roles.get(team)
        if team_role_id:
            team_role = guild.get_role(team_role_id)
            await member.remove_roles(team_role)
    except:
        pass

# Give access to dead channel
dead_channel_id = game.team_channels.get("dead")
if dead_channel_id:
    dead_channel = await bot.fetch_channel(dead_channel_id)
    # Send welcome message
    await dead_channel.send(f"💀 {eliminated_name} has joined the afterlife...")
```

---

## Phase 4: Game Start with Roles

### 4.1 Update `/start` Command
**File**: `cogs/game_management.py`

Modify `start_game()`:
```python
@app_commands.command(name="start")
async def start_game(self, interaction: discord.Interaction):
    # ... existing checks ...

    # NEW: Assign roles
    from utils import roles as role_utils
    game.roles = role_utils.assign_roles(list(game.players))

    # NEW: Create Discord roles
    from utils import role_manager
    game.discord_roles = await role_manager.create_game_roles(guild, game.name)

    # NEW: Create private channels
    saboteur_channel, dead_channel = await forum_manager.create_private_channels(
        guild, game.name, mod_role, bot_member
    )
    game.team_channels = {
        "saboteurs": saboteur_channel.id,
        "dead": dead_channel.id
    }

    # NEW: Assign Discord roles to players
    saboteurs = []
    for player_id, role_name in game.roles.items():
        if player_id < 0:  # Skip NPCs
            continue

        team = game.get_player_team(player_id)
        role_id = game.discord_roles.get(team)

        try:
            member = await guild.fetch_member(player_id)
            await role_manager.assign_player_role(guild, member, role_id)

            # Track saboteurs for channel access
            if team == "saboteur":
                saboteurs.append(member)
        except:
            pass

    # NEW: Give saboteurs access to saboteur channel
    for member in saboteurs:
        await saboteur_channel.set_permissions(
            member,
            view_channel=True,
            send_messages=True
        )

    # NEW: Send role DMs to players
    for player_id, role_name in game.roles.items():
        if player_id < 0:  # Skip NPCs
            continue

        try:
            user = await self.bot.fetch_user(player_id)
            role_info = role_utils.ROLES[role_name]

            dm_embed = discord.Embed(
                title=f"🎮 {game.name} - Your Role",
                description=f"{role_info['emoji']} **{role_name}**\n\n{role_info['description']}",
                color=discord.Color.red() if role_info['team'] == "saboteur" else discord.Color.blue()
            )

            if role_info['team'] == "saboteur":
                dm_embed.add_field(
                    name="🔴 Saboteur Channel",
                    value=f"Coordinate with fellow saboteurs in {saboteur_channel.mention}",
                    inline=False
                )

            await user.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled

    # ... rest of existing start logic ...
```

---

## Phase 5: UI Updates

### 5.1 Role Reveal on Death
**File**: `utils/game_logic.py`

Update `format_day_end_message()`:
```python
def format_day_end_message(eliminated_id: Optional[int], result_type: str,
                           tally: Dict, user_names: Dict[int, str],
                           roles: Dict[int, str], day: int) -> str:
    """Format end-of-day announcement with role reveal."""
    lines = [f"🌙 **Day {day} has ended!**\n"]

    if result_type == "elimination":
        eliminated_name = user_names.get(eliminated_id, f"User {eliminated_id}")
        eliminated_role = roles.get(eliminated_id, "Unknown")
        role_emoji = ROLES.get(eliminated_role, {}).get("emoji", "")
        votes = tally.get(eliminated_id, 0)

        lines.append(
            f"**{eliminated_name}** has been eliminated with **{votes}** vote{'s' if votes != 1 else ''}!\n"
            f"They were: {role_emoji} **{eliminated_role}**"
        )

    # ... rest of existing logic ...
```

### 5.2 Game End with Team Victory
**File**: `cogs/moderator.py`

Update game end announcement:
```python
# In end_day() when game ends:
if win_team == "crew":
    title = "🏆 Crew Victory!"
    description = "The crew has successfully eliminated all saboteurs!\n\n"
    color = discord.Color.blue()
elif win_team == "saboteur":
    title = "🔴 Saboteur Victory!"
    description = "The saboteurs have taken control of the ship!\n\n"
    color = discord.Color.red()

# List winners by role
winner_list = []
for player_id in alive_players:
    name = user_names.get(player_id)
    role = game.roles.get(player_id)
    role_emoji = ROLES.get(role, {}).get("emoji", "")
    winner_list.append(f"{role_emoji} {name} ({role})")

description += "**Winners:**\n" + "\n".join(winner_list)

# Show all roles
description += "\n\n**All Players:**\n"
for player_id in game.players:
    name = user_names.get(player_id)
    role = game.roles.get(player_id)
    role_emoji = ROLES.get(role, {}).get("emoji", "")
    status = "💀" if player_id not in alive_players else "✅"
    description += f"{status} {role_emoji} {name} - {role}\n"
```

---

## Phase 6: Special Abilities (Future)

### 6.1 Night Phase Commands (Optional for v2)
Commands to add later:
- `/investigate @player` - Security Officer only
- `/protect @player` - Engineer only
- `/night_kill @player` - Saboteurs only (if adding night kills)

### 6.2 Night/Day Cycle (Optional for v2)
- Add `phase` field to Game: "day" or "night"
- `/end_day` transitions to night
- `/end_night` transitions to next day
- Lock discussion during night, allow only private actions

---

## Phase 7: Cleanup on Game End

### 7.1 Delete Private Channels
**File**: `cogs/moderator.py`

```python
# When game ends, clean up private channels
saboteur_channel_id = game.team_channels.get("saboteurs")
dead_channel_id = game.team_channels.get("dead")

if saboteur_channel_id:
    try:
        channel = await self.bot.fetch_channel(saboteur_channel_id)
        await channel.delete()
    except:
        pass

if dead_channel_id:
    try:
        channel = await self.bot.fetch_channel(dead_channel_id)
        await channel.delete()
    except:
        pass

# Delete Discord roles
await role_manager.cleanup_game_roles(guild, list(game.discord_roles.values()))
```

---

## Implementation Order

### Sprint 1: Foundation
1. ✅ Create `utils/roles.py` with role definitions
2. ✅ Update `models/game.py` with role fields
3. ✅ Implement role assignment logic
4. ✅ Update win condition logic

### Sprint 2: Channels & Roles
5. ✅ Create `utils/role_manager.py`
6. ✅ Update `utils/forum_manager.py` with private channel creation
7. ✅ Test channel/role creation manually

### Sprint 3: Integration
8. ✅ Update `/start` to assign roles and create channels
9. ✅ Send role DMs to players
10. ✅ Update `/end_day` to handle death permissions
11. ✅ Update game end messages with role reveals

### Sprint 4: Polish
12. ✅ Add role reveals on death
13. ✅ Update embeds with team victory
14. ✅ Cleanup channels/roles on game end
15. ✅ Test full game flow with NPCs

### Sprint 5: Special Abilities (Future)
16. ⏳ Add Security Officer investigation
17. ⏳ Add Engineer protection
18. ⏳ (Optional) Add night phase system

---

## Testing Plan

### Test Case 1: Small Game (4 players)
- 1 Saboteur, 3 Crew Members
- Verify role assignment
- Verify saboteur channel access
- Eliminate saboteur → Crew wins

### Test Case 2: Medium Game (8 players)
- 2 Saboteurs, 1 Security Officer, 1 Engineer, 4 Crew
- Verify special roles assigned
- Eliminate crew until saboteurs ≥50% → Saboteurs win

### Test Case 3: NPC Testing
- Create game with 3 NPCs + 1 real player
- Use `/npc_vote` to test elimination
- Verify role reveals work
- Verify dead channel access

---

## Database Migration

Since we're adding new fields to `Game`, need to handle:
- Existing games won't have `roles`, `team_channels`, `discord_roles`
- Add defaults in `database.py` when loading old games
- Consider version field in saved games

---

## UI/UX Improvements

### Role Assignment Preview
Before game starts, show role distribution:
```
📊 Role Distribution (8 players):
- 👨‍🚀 Crew Member: 4
- 🔪 Saboteur: 2
- 🔍 Security Officer: 1
- 🛡️ Engineer: 1
```

### Team Status Command
Add `/team_status` (saboteurs only, in saboteur channel):
```
🔴 Saboteur Team Status
Alive Saboteurs: 🔪 Alice, 🔪 Bob
Alive Crew: 6
Need to eliminate: 4 more crew to win
```

---

## Balance Notes

### Recommended Player Counts
- **4-5 players**: 1 saboteur, rest crew
- **6-7 players**: 1 saboteur, 1 security officer, rest crew
- **8-9 players**: 2 saboteurs, 1 security officer, 1 engineer, rest crew
- **10-12 players**: 3 saboteurs, 1 security officer, 1 engineer, rest crew
- **13+ players**: Add more saboteurs (maintain ~25% ratio)

### Future Roles to Consider
- **Vigilante**: Can eliminate one player during the game
- **Godfather**: Saboteur immune to investigation
- **Jester**: Wins if they get themselves eliminated (chaos role)
- **Doctor**: Can revive one player per game
