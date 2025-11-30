# CSS Solaris - Design Document

## Overview
CSS Solaris is a Discord bot for running Mafia-like social deduction games. The game operates on day/night cycles where players vote to eliminate suspects, similar to games like Mafia, Werewolf, Secret Hitler, and Coup.

## Game Flow

### 1. Game Creation
- A user runs `/new_game <game_name>` to create a new game
- This creates a signup forum post/thread
- The game enters the "Signup" phase

### 2. Player Signup
- Players use `/join` in the signup thread to join the game
- A pinned/tracked message lists all current players
- The game creator/moderator can start the game when ready

### 3. Game Start
- Moderator runs `/start <game_name>`
- Creates two forum channels:
  - `<game_name>: Day 1 (Votes)`
  - `<game_name>: Day 1 (Discussion)`
- Players are assigned to groups (for now: just "In" group - all players)
- Future: Role assignment (e.g., Vigilante, Mafia, Villager)

### 4. Day Cycle
- **Discussion Phase**: Players discuss in the Discussion channel
- **Voting Phase**: Players use `/vote @username` in the Votes channel
  - Players can change votes by voting again
  - Special votes: `/vote Veto` or `/vote Abstain`
    - **Veto**: Player doesn't want to vote (counts as non-participation)
    - **Abstain**: Player wants to abstain (counts as a vote to eliminate nobody)

### 5. End Day
- Moderator runs `/end_day <game_name>`
- Bot counts all votes
- Announces the player with the most votes
- Creates next day's forum channels (Day 2, Day 3, etc.)
- Archives/locks previous day's channels

### 6. Night Cycle (Future)
- Players with night actions can perform them
- For now: Skip or minimal implementation

## Architecture

### Data Storage Strategy
Given the requirement to use Discord messages as the primary storage mechanism:

#### Game State Storage
Store game state in a local text file (`games_db.txt` or JSON format):
```json
{
  "game_name": {
    "status": "signup|active|ended",
    "creator_id": "discord_user_id",
    "signup_thread_id": "channel_id",
    "current_day": 1,
    "players": ["user_id_1", "user_id_2"],
    "channels": {
      "day_1": {
        "votes_channel_id": "channel_id",
        "discussion_channel_id": "channel_id",
        "votes_message_id": "message_id"
      }
    },
    "roles": {
      "user_id_1": "villager",
      "user_id_2": "vigilante"
    }
  }
}
```

#### Message-Based Tracking
- **Signup Thread**: Keep an editable message listing all players
- **Votes Channel**: Keep an editable message showing current vote tally
- Format:
  ```
  📊 Current Votes - Day 1

  @Player1 → @SuspectA
  @Player2 → Abstain
  @Player3 → @SuspectA
  @Player4 → Veto

  Tally:
  @SuspectA: 2 votes
  Abstain: 1 vote
  Not voted: 3 players
  ```

### File Structure
```
css_solaris/
├── .env                    # Environment variables (TOKEN, GUILD_ID)
├── .env.example            # Template for .env
├── .gitignore             # Git ignore file
├── requirements.txt        # Python dependencies
├── DESIGN.md              # This file
├── claude.md              # Project objectives
├── README.md              # User-facing documentation
├── bot.py                 # Main bot entry point
├── data/
│   └── games.json         # Game state database
├── cogs/
│   ├── __init__.py
│   ├── game_management.py # /new_game, /start commands
│   ├── player_actions.py  # /join, /vote commands
│   └── moderator.py       # /end_day, admin commands
├── utils/
│   ├── __init__.py
│   ├── database.py        # Database read/write utilities
│   ├── game_logic.py      # Vote counting, game state logic
│   └── permissions.py     # Permission checks
└── models/
    ├── __init__.py
    ├── game.py            # Game class
    ├── player.py          # Player class
    └── role.py            # Role classes (for future)
```

## Commands Specification

### User Commands

#### `/new_game <game_name>`
- **Permission**: Any user
- **Description**: Creates a new game and opens signup
- **Actions**:
  1. Check if game name already exists
  2. Create a forum post in designated signup channel
  3. Store game state with status "signup"
  4. Post initial signup message
- **Response**: "Game '{game_name}' created! Players can now `/join` in this thread."

#### `/join`
- **Permission**: Any user (in signup thread only)
- **Description**: Join the current game
- **Actions**:
  1. Verify command is in a signup thread
  2. Check if user already joined
  3. Add user to player list
  4. Update signup message
- **Response**: "{user} has joined the game! (X/Y players)"

#### `/vote <target>`
- **Permission**: Players in active game (in votes channel only)
- **Description**: Vote for a player to eliminate
- **Targets**: @mention, "Veto", "Abstain"
- **Actions**:
  1. Verify command is in active votes channel
  2. Verify user is a player in this game
  3. Record/update vote
  4. Update votes tracking message
- **Response**: "Your vote has been recorded."

### Moderator Commands

#### `/start <game_name>`
- **Permission**: Game creator, Admin, Moderator
- **Description**: Start the game and create Day 1 channels
- **Actions**:
  1. Verify game exists and is in "signup" status
  2. Verify minimum player count (e.g., 3+ players)
  3. Create forum channels for Day 1
  4. Assign roles (for now: all "villager", placeholder for future)
  5. Update game status to "active"
  6. Lock signup thread
- **Response**: "Game started! Day 1 begins now."

#### `/end_day <game_name>`
- **Permission**: Game creator, Admin, Moderator
- **Description**: End the current day, tally votes, advance to next day
- **Actions**:
  1. Verify game exists and is active
  2. Count all votes
  3. Determine elimination (most votes wins, ties go to no elimination)
  4. Announce results in both channels
  5. Create Day N+1 channels
  6. Lock/archive previous day's channels
- **Response**: "Day X has ended. {Player} has been eliminated with Y votes."

## Vote Counting Logic

```python
def count_votes(votes_dict):
    """
    votes_dict = {
        "user_id_1": "target_user_id_2",
        "user_id_2": "ABSTAIN",
        "user_id_3": "VETO",
        "user_id_4": "target_user_id_2"
    }
    """
    tally = {}
    veto_count = 0
    abstain_count = 0

    for voter, target in votes_dict.items():
        if target == "VETO":
            veto_count += 1
        elif target == "ABSTAIN":
            abstain_count += 1
        else:
            tally[target] = tally.get(target, 0) + 1

    # Find player with most votes
    if tally:
        eliminated = max(tally, key=tally.get)
        max_votes = tally[eliminated]

        # Check for ties
        tied_players = [p for p, v in tally.items() if v == max_votes]
        if len(tied_players) > 1:
            return None, "tie", tally  # No elimination on tie

        return eliminated, max_votes, tally

    return None, "no_votes", {}
```

## Role System (Future Implementation)

### Base Role Class
```python
class Role:
    name: str
    team: str  # "town", "mafia", "neutral"
    can_vote: bool = True
    night_action: callable = None
```

### Example Roles
- **Villager**: No special abilities, town team
- **Vigilante**: Can eliminate one player at night (town team)
- **Mafia**: Knows other mafia, kills at night (mafia team)
- **Detective**: Can investigate one player per night (town team)

### Role Assignment
- Store in game state
- Private role reveals via DM
- Role-specific channels (e.g., Mafia private channel)

## Technical Considerations

### Discord.py Setup
- Use `discord.py` 2.x with slash commands
- Use application commands (interactions)
- Requires bot permissions:
  - Manage Channels (create forums)
  - Send Messages
  - Embed Links
  - Manage Messages (edit tracking messages)
  - Read Message History

### Error Handling
- Invalid game names
- Duplicate game creation
- Users not in game trying to vote
- Commands used in wrong channels
- Insufficient permissions

### Scalability
- Current design: File-based storage (games.json)
- Future: SQLite or PostgreSQL
- Support multiple concurrent games

### Testing Strategy
- Unit tests for vote counting logic
- Integration tests for command workflows
- Manual testing in Discord test server

## Future Enhancements
1. Role system implementation
2. Night cycle mechanics
3. Private role channels
4. Game history/statistics
5. Spectator mode
6. Custom game settings (vote timer, player limits)
7. Web dashboard for game state
8. Replay/log system

## Security & Permissions
- Game creator stored on creation
- Moderator role check for admin commands
- Prevent vote manipulation (one vote per player)
- Rate limiting on commands
- Input validation (game names, mentions)

## Environment Variables
```
DISCORD_BOT_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id (for testing)
SIGNUP_CHANNEL_ID=channel_id_for_signups
MODERATOR_ROLE_ID=role_id_for_moderators (optional)
```
