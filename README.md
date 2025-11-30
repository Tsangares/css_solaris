# CSS Solaris - Discord Mafia Bot

A Discord bot for running social deduction games similar to Mafia, Werewolf, Secret Hitler, and Coup.

## Features

- Create and manage multiple concurrent games
- Day/night cycle gameplay
- Vote tracking with real-time updates
- Support for Abstain and Veto votes
- Automatic vote counting and elimination
- Clean, organized game channels
- Role system (planned for future)

## Commands

### Player Commands

| Command | Description |
|---------|-------------|
| `/new_game <name>` | Create a new game |
| `/join` | Join a game during signup |
| `/vote @player` | Vote to eliminate a player |
| `/vote Abstain` | Vote to eliminate nobody |
| `/vote Veto` | Don't participate in voting |

### Moderator Commands

| Command | Description |
|---------|-------------|
| `/start <name>` | Start a game (requires moderator or game creator) |
| `/end_day <name>` | End current day and count votes (requires moderator or game creator) |

## Setup

### Prerequisites

- Python 3.8 or higher
- A Discord account
- A Discord server where you have admin permissions

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Under "Privileged Gateway Intents", enable:
   - Server Members Intent
   - Message Content Intent
5. Click "Reset Token" to get your bot token (save this for later)
6. Go to "OAuth2" > "URL Generator"
7. Select scopes: `bot`, `applications.commands`
8. Select bot permissions:
   - Manage Channels
   - Send Messages
   - Embed Links
   - Manage Messages
   - Read Message History
   - Use Slash Commands
9. Copy the generated URL and open it in your browser to invite the bot to your server

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
{BotName} has connected to Discord!
Bot is in X guild(s)
Synced commands to guild {GUILD_ID}
```

## Usage

### Creating a Game

1. Use `/new_game <game_name>` to create a new game
   - Example: `/new_game Jacks`

2. Players join using `/join` in the signup thread

3. Moderator starts the game with `/start <game_name>`
   - Example: `/start Jacks`
   - This creates Day 1 voting and discussion channels

### Playing a Day

1. Players discuss in the discussion channel
2. Players vote in the voting channel using `/vote @player`
   - Can change votes by voting again
   - Can `/vote Abstain` to vote for no elimination
   - Can `/vote Veto` to not participate

3. Moderator ends the day with `/end_day <game_name>`
   - Bot counts votes and announces results
   - Player with most votes is eliminated (ties = no elimination)
   - Creates Day 2 channels automatically

4. Repeat until game ends

## Project Structure

```
css_solaris/
├── bot.py                 # Main bot entry point
├── cogs/                  # Command modules
│   ├── game_management.py # Game creation/starting
│   ├── player_actions.py  # Player commands (join, vote)
│   └── moderator.py       # Admin commands (end_day)
├── models/                # Data structures
│   ├── game.py           # Game class
│   ├── player.py         # Player class
│   └── role.py           # Role classes (future)
├── utils/                 # Helper functions
│   ├── database.py       # Database operations
│   ├── game_logic.py     # Vote counting logic
│   └── permissions.py    # Permission checks
└── data/                  # Game state storage
    └── games.json        # Created at runtime
```

## Vote Counting Rules

1. **Majority**: Player with most votes is eliminated
2. **Ties**: No elimination occurs
3. **Abstain**: Counted as a vote for no elimination
4. **Veto**: Not counted in vote total
5. **No Votes**: No elimination occurs

## Future Features

- [ ] Role system (Vigilante, Mafia, Detective, etc.)
- [ ] Night cycle with special abilities
- [ ] Private role channels
- [ ] Game statistics and history
- [ ] Customizable game settings
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

**Bot doesn't respond to commands:**
- Make sure the bot is online (check Discord)
- Verify bot has correct permissions
- Check that intents are enabled in Developer Portal
- Wait a few minutes for commands to sync (or specify GUILD_ID for instant sync)

**"Missing Permissions" error:**
- Ensure bot has required permissions (see Setup step 1.8)
- Check channel-specific permissions

**Commands not appearing:**
- Wait up to 1 hour for global command sync
- Or specify GUILD_ID in .env for instant sync during development

**Game state lost on restart:**
- Check that `data/games.json` exists and is readable
- Verify write permissions in data directory

## License

[To be decided - MIT, GPL, etc.]

## Credits

Created for running CSS Solaris games on Discord.

Inspired by Mafia, Werewolf, Secret Hitler, and Coup.

## Support

For issues and feature requests, please open an issue on GitHub.
