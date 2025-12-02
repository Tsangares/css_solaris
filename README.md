# CSS Solaris - Discord Mafia Bot

A Discord bot for running social deduction games similar to Mafia, Werewolf, Secret Hitler, and Coup.

## Features

- Create and manage multiple concurrent games using Discord Forum Channels
- Automatic forum channel creation (Game Lobby, Discussions, Voting)
- Day/night cycle gameplay
- Vote tracking with real-time updates
- Support for Abstain and Veto votes
- Automatic vote counting and elimination
- Clean, organized forum threads for each game and day
- NPC system for solo testing with bot-controlled players
- Role-based moderator system
- Easy setup with `/setup` command

## Commands

### Setup Commands

| Command | Description |
|---------|-------------|
| `/setup` | Initial server setup - creates moderator role and forum channels (Admin only) |
| `/invite` | Get the bot invite link with all required permissions |

### Player Commands

| Command | Description |
|---------|-------------|
| `/new_game <name>` | Create a new game (creates a forum post in Game Lobby) |
| `/join` | Join a game during signup (use in the game's signup thread) |
| `/players` | List all players in the current game (alive and eliminated) |
| `/vote @player` | Vote to eliminate a player |
| `/vote Abstain` | Vote to eliminate nobody |
| `/vote Veto` | Don't participate in voting |

### Moderator Commands

| Command | Description |
|---------|-------------|
| `/start` | Start a game (use in signup thread, requires moderator or game creator) |
| `/end_day` | End current day and count votes (use in discussion thread, requires moderator or game creator) |

### NPC Commands

These commands are available to all users for creating and controlling NPC (bot-controlled) players:

| Command | Description |
|---------|-------------|
| `/npc_create <name> <persona>` | Create an NPC player for testing |
| `/npc_list` | List all NPCs |
| `/npc_delete <name>` | Delete an NPC |
| `/npc_join <npc_name>` | Make an NPC join a game (use in signup thread) |
| `/npc_vote <npc_name> <target>` | Make an NPC cast a vote (use in discussion/votes thread) |
| `/npc_say <npc_name> <message>` | Make an NPC send a message in the discussion |

## Setup

### Prerequisites

- Python 3.8 or higher
- A Discord account
- A Discord server where you have admin permissions

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. **IMPORTANT: Enable Privileged Intents** - Under "Privileged Gateway Intents", enable:
   - ✅ **Server Members Intent** (Required!)
   - ✅ **Presence Intent** (Optional but recommended)
   - ❌ Message Content Intent (Not needed)

   **Without Server Members Intent enabled, the bot will not start!**

5. Click "Reset Token" to get your bot token (save this for later)

**Note:** Don't worry about manually creating an invite link yet - the bot will generate one with all the correct permissions after setup!

### 2. Install the Bot

```bash
# Clone or download this repository
cd css_solaris

# Create a virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your bot token:
   ```env
   DISCORD_BOT_TOKEN=your_actual_bot_token_here
   GUILD_ID=your_guild_id_here  # Optional: for faster dev
   ```

3. To get your Guild ID:
   - Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
   - Right-click your server and click "Copy ID"

### 4. Run the Bot

```bash
python bot.py
```

You should see:
```
==================================================
✅ CSS Solaris has connected to Discord!
📊 Bot is in X guild(s)
   - YourServerName (ID: ...)
✅ Synced commands to guild {GUILD_ID}
🚀 Bot is ready! Use /setup to get started.
==================================================
```

### 5. Invite and Setup

#### Option A: First Time Setup (Recommended)

If the bot is already in your test server but doesn't have permissions:

1. In Discord, run `/invite` to get the bot invite link with all required permissions
2. Kick the current bot from your server
3. Use the invite link to re-add the bot with proper permissions
4. Run `/setup` to create forum channels and moderator role

#### Option B: Manual Permissions

If you prefer to manually grant permissions:

1. Go to Server Settings → Roles
2. Find your bot's role (usually named "CSS Solaris")
3. Enable these permissions:
   - ✅ Manage Roles
   - ✅ Manage Channels
   - ✅ Manage Threads
   - ✅ Create Public Threads
   - ✅ Send Messages in Threads
   - ✅ Send Messages
   - ✅ Embed Links
4. Run `/setup` in Discord

#### What `/setup` Does:

- ✅ Creates "CSS Solaris Moderator" role
- ✅ Creates "Game Lobby" forum channel
- ✅ Creates "Game Discussions" forum channel
- ✅ Creates "Game Voting" forum channel (read-only for everyone)
- ✅ Verifies all permissions are correct

After setup, assign the "CSS Solaris Moderator" role to users who should be able to start/manage games!

**Note:** The Game Voting forum is automatically set to be read-only:
- **@everyone**: Can view but cannot post (read-only)
- **Moderators**: Can view but cannot post (read-only)
- **Bot**: Can view, post, and manage threads

This ensures only the bot can update vote tallies while everyone can see the current voting status.

## Usage

### Creating a Game

1. Use `/new_game <game_name>` to create a new game
   - Example: `/new_game Jacks`
   - This creates a forum post in the "Game Lobby" forum

2. Players join using `/join` in the signup thread
   - NPCs will appear with a 🤖 emoji prefix

3. Moderator starts the game with `/start` (in the signup thread)
   - This creates Day 1 threads in both "Game Discussions" and "Game Voting" forums

### Playing a Day

1. Players discuss in the discussion thread
2. Players vote **in the discussion thread** using `/vote @player` or `/vote NPCName`
   - Vote autocomplete shows available players and NPCs
   - Can change votes by voting again
   - Can `/vote Abstain` to vote for no elimination
   - Can `/vote Veto` to not participate
   - Vote tallies are tracked in a read-only voting forum (visible to everyone)

3. Moderator ends the day with `/end_day` **in the discussion thread**
   - Bot counts votes and announces results
   - Player with most votes is eliminated (ties = no elimination)
   - Creates Day 2 threads automatically
   - Old threads are locked and archived

4. Repeat until game ends

**Note:** The voting channel is read-only for everyone (only the bot can post). All discussion and voting happens in the discussion thread. When someone votes, a public confirmation appears with a link to the vote tally that everyone can view.

### Testing with NPCs

For solo testing before running a real game:

1. Create some test NPCs:
   ```
   /npc_create Alice Clever strategist, always thinking ahead
   /npc_create Bob Quiet observer who rarely speaks
   /npc_create Charlie Aggressive player, quick to accuse
   ```

2. Create a test game and have NPCs join (run these in the signup thread):
   ```
   /new_game TestGame
   (Now go into the TestGame signup thread)
   /npc_join Alice
   /npc_join Bob
   /npc_join Charlie
   /join (join yourself too!)
   ```

3. Start and play (in the signup thread):
   ```
   /start
   ```

   Then in the discussion thread:
   ```
   /npc_say Alice I think Bob is acting suspicious...
   /npc_say Bob That's ridiculous! I'm innocent!
   /npc_vote Alice Bob
   /npc_vote Charlie Abstain
   /vote Alice (your vote)
   /end_day
   ```

4. NPCs appear alongside real players in all game displays!

**Key Features:**
- `/npc_say` makes NPCs speak in character with their persona (autocomplete for NPC names)
- `/npc_vote` has dropdown autocomplete for both NPC names and vote targets
- `/npc_join` and `/npc_delete` also have autocomplete for easy NPC selection
- NPCs can be voted for by name using `/vote Alice` (autocomplete supported)
- Vote tracking is visible to everyone in the read-only voting forum
- **Anyone can create and control NPCs** - no special permissions required!

## Project Structure

```
css_solaris/
├── bot.py                  # Main bot entry point
├── cogs/                   # Command modules
│   ├── game_management.py  # Game creation/starting
│   ├── player_actions.py   # Player commands (join, vote, players)
│   ├── moderator.py        # Admin commands (setup, end_day, invite)
│   └── npc_commands.py     # NPC commands (available to all users)
├── models/                 # Data structures
│   ├── game.py             # Game class
│   ├── npc.py              # NPC class for testing
│   └── role.py             # Role classes (future)
├── utils/                  # Helper functions
│   ├── database.py         # Database operations (games & NPCs)
│   ├── game_logic.py       # Vote counting logic
│   ├── permissions.py      # Permission checks
│   ├── forum_manager.py    # Forum channel creation
│   └── bot_utils.py        # Invite link generation & permission checks
└── data/                   # Game state storage
    ├── games.json          # Created at runtime
    └── npcs.json           # Created at runtime
```

## Vote Counting Rules

1. **Majority**: Player with most votes is eliminated
2. **Ties**: No elimination occurs
3. **Abstain**: Counted as a vote for no elimination
4. **Veto**: Not counted in vote total
5. **No Votes**: No elimination occurs

## Future Features

### 🚀 Coming Soon: Full Role System
See `ROLES_IMPLEMENTATION_PLAN.md` for detailed implementation plan.

**Planned:**
- **Space-themed Mafia**: Crew vs Saboteurs (25% saboteurs)
- **Roles**: Crew Member, Saboteur, Security Officer (detective), Engineer (protector)
- **Private Channels**: Saboteur coordination channel, Dead player afterlife channel
- **Discord Roles**: Automatic role assignment with permission management
- **Win Conditions**: Crew wins if all saboteurs eliminated, Saboteurs win at 50% control
- **Role Reveals**: On death, player's role is publicly announced
- **Team Victory**: Winning team and all roles revealed at game end

### Other Future Ideas
- [ ] Night cycle with special abilities (investigate, protect)
- [ ] Game statistics and history
- [ ] Customizable game settings (role ratios, special rules)
- [ ] Spectator mode
- [ ] Web dashboard

## Development

See `DESIGN.md` for detailed architecture and design decisions.

See `claude.md` for project objectives and goals.

### Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

### Testing

To test the bot:
1. Create a test Discord server
2. Invite your bot
3. Run through a full game with at least 3 test accounts

## Troubleshooting

**"PrivilegedIntentsRequired" error when starting bot:**
This is the most common issue! You need to enable Server Members Intent:
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Go to "Bot" section
4. Scroll down to "Privileged Gateway Intents"
5. Enable **Server Members Intent** toggle
6. Save changes
7. Restart your bot

**Bot doesn't respond to commands:**
- Make sure the bot is online (check Discord)
- Verify bot has correct permissions (run `/invite` to get proper invite link)
- Check that Server Members Intent is enabled in Developer Portal
- Wait a few minutes for commands to sync (or specify GUILD_ID for instant sync)

**"Missing Permissions" error:**
- Run `/setup` - it will tell you exactly which permissions are missing
- Run `/invite` to get a bot invite link with all required permissions
- Option: Kick and re-invite the bot using the link from `/invite`
- Option: Manually grant permissions in Server Settings → Roles

**"Owner ID=None" or permission check failures:**
- Make sure **Server Members Intent** is enabled in Discord Developer Portal
- Restart the bot after enabling intents

**Commands not appearing:**
- Wait up to 1 hour for global command sync
- Or specify GUILD_ID in .env for instant sync during development

**Game state lost on restart:**
- Check that `data/games.json` and `data/npcs.json` exist and are readable
- Verify write permissions in data directory

**Forum channels not being created:**
- Make sure the bot has "Manage Channels" permission
- Run `/setup` which will create the required forums automatically

## License

[To be decided - MIT, GPL, etc.]

## Credits

Created for running CSS Solaris games on Discord.

Inspired by Mafia, Werewolf, Secret Hitler, and Coup.

## Support

For issues and feature requests, please open an issue on GitHub.
