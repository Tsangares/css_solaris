# CSS Solaris

A Discord bot that runs social deduction games in the tradition of Mafia, Werewolf, and Secret Hitler. Players are secretly assigned as Crew or Saboteurs and must use discussion, deception, and deduction to win. The bot handles game management, vote tracking, role assignment, day/night cycles, and private team channels so you can focus on the gameplay.

## How It Works

One player acts as the **MC** (game master) and creates a game. Other players join, and the bot secretly assigns everyone as either **Crew** or **Saboteur** via DM. During the day, players discuss and vote to eliminate suspects. At night, saboteurs secretly choose someone to kill. The crew wins by eliminating all saboteurs. The saboteurs win by reaching numerical parity.

## Features

- **Full day/night cycle** with vote elimination and saboteur night kills
- **Private channels** for saboteur coordination and eliminated player spectating
- **MC toolkit** with narration, instant kills (/smite), resurrections (/revive), and a private workspace
- **NPC system** for testing or filling games with bot-controlled players
- **Vote ledger** with live tally, bar chart, and Discord timestamps
- **Configurable win conditions**, saboteur ratio, and day/night timers
- **Per-game roles and permissions** that don't reveal team allegiance
- **AI image generation** via Gemini for posters and artwork

## Quick Start

```bash
git clone https://github.com/Tsangares/css_solaris.git
cd css_solaris
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env  # Add your Discord bot token
.venv/bin/python bot.py
```

Then in Discord: `/setup` to create channels, `/game MyGame` to start.

### Discord Bot Setup

1. Create a bot at the [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable **Server Members Intent** under Privileged Gateway Intents
3. Invite with all permissions: Manage Channels, Manage Roles, Manage Messages, Manage Threads, Create Public/Private Threads, Send Messages (in Threads), Embed Links, Attach Files, Read Message History, Mention Everyone

## Commands

### Game Flow
| Command | Who | Description |
|---------|-----|-------------|
| `/game <name>` | Anyone | Create a new game with signup thread and private channels |
| `/join` | Anyone | Join during signup phase |
| `/start` | MC | Assign roles, create Day 1 threads, DM everyone their role |
| `/vote <target>` | Players | Vote to eliminate (day phase only) |
| `/endday` | MC | Tally votes, eliminate player, enter night |
| `/kill <target>` | Saboteurs | Choose night kill target (night phase) |
| `/endnight` | MC / Saboteurs | Execute kill, reveal roles, start next day |
| `/players` | Anyone | Show alive and eliminated players |

### MC Tools
| Command | Description |
|---------|-------------|
| `/narrate <text or message link>` | Send styled narration (with images) to discussion |
| `/say <message>` | Post as bot or as NPC (`as_npc:name`) |
| `/smite @player "reason"` | Instantly eliminate a player with a story event |
| `/revive @player` | Bring an eliminated player back to life |

### NPC Management
| Command | Description |
|---------|-------------|
| `/npc create <name> <persona>` | Create an NPC |
| `/npc list` | List all NPCs |
| `/npc delete <name>` | Delete an NPC |
| `/npc join <name>` | Add NPC to a game |
| `/npc vote <name> <target>` | Make NPC cast a vote |

### Administration
| Command | Description |
|---------|-------------|
| `/setup` | Create forums, mod role, organize channels |
| `/configure` | Interactive server and game settings panel |
| `/mod add/remove/list` | Manage per-game moderators |
| `/panel` | View game state overview |
| `/purge` | Delete all games, threads, roles, categories |
| `/sync` | Clear duplicate commands |
| `/invite` | Bot invite link with correct permissions |
| `/poster <description>` | AI image generation (Gemini 2.0 Flash) |

## Game Structure

```
DAY: Players discuss and /vote -> MC runs /endday -> player eliminated (role hidden)
NIGHT: Saboteurs /kill in private channel -> MC or saboteurs run /endnight
DAWN: Yesterday's role revealed, night kill announced, new day begins
```

### Win Conditions (configurable)
- **Crew wins** when all saboteurs are eliminated
- **Saboteurs win** when they control 50% or more of alive players

### Discord Channel Layout
```
CSS SOLARIS (category)
  game-lobby         Forum for game signups
  game-discussions    Forum for daily discussion threads
  game-voting         Forum for vote tally threads

🎮 GameName (category, per game)
  🎭-mc-booth        MC private workspace
  🔴-saboteurs       Saboteur team chat
  💀-afterlife        Eliminated player spectating
```

## Configuration

### Environment Variables (.env)
```
DISCORD_BOT_TOKEN=       # Required
GUILD_ID=                # Recommended for instant command sync
GEMINI_API_KEY=          # Optional, for /poster image generation
```

### Game Settings (via /configure)
- `player_say_enabled` - Allow players to use /say
- `day_duration_hours` - Auto-lock timer (default 24h)
- `win_crew` - Crew win condition
- `win_saboteur` - Saboteur win condition
- `saboteur_ratio` - Fraction of players assigned as saboteurs (default 0.33)

## Tech Stack

- Python 3.13 + discord.py
- JSON file persistence
- Gemini 2.0 Flash for image generation
- systemd for process management

## License

MIT
