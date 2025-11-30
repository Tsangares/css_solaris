# CSS Solaris - Project Objectives & Goals

## Project Purpose
CSS Solaris is a Discord bot designed to facilitate social deduction games similar to Mafia, Werewolf, Secret Hitler, and Coup. The bot automates game management, vote tracking, and phase transitions, allowing communities to easily run engaging social deduction games within Discord.

## Primary Goals

### 1. Simplicity & Usability
- Intuitive slash commands that are easy to remember
- Clear feedback for all user actions
- Minimal setup required for game creators
- Graceful error handling with helpful messages

### 2. Discord-Native Experience
- Leverage Discord's forum channel feature for organized game threads
- Use Discord's native mentions for voting
- Maintain game state through edited messages (visible to players)
- Future: Use Discord's thread features for private role channels

### 3. Data Persistence & Reliability
- Simple file-based storage for initial version (games.json)
- Resilient to bot restarts (state persisted to disk)
- Message-based tracking as backup/visual confirmation
- Easy migration path to database in future

### 4. Extensibility
- Modular cog-based architecture for easy feature addition
- Role system designed for future expansion
- Clean separation between game logic and Discord interface
- Plugin architecture for custom game modes (future)

## Core Features (MVP - Minimum Viable Product)

### Phase 1: Basic Game Management
- [x] Create new games with `/new_game`
- [x] Player signup with `/join`
- [x] Start games with `/start`
- [x] Vote tracking with `/vote`
- [x] End day cycle with `/end_day`
- [x] Basic vote counting (majority wins, handle ties)
- [x] Veto and Abstain vote options

### Phase 2: Role System (Future)
- [ ] Define role classes (Villager, Vigilante, Mafia, Detective)
- [ ] Role assignment on game start
- [ ] Private role reveals via DM
- [ ] Role-specific abilities
- [ ] Night cycle for night actions

### Phase 3: Enhanced Features (Future)
- [ ] Game settings (timers, player limits, voting rules)
- [ ] Spectator mode
- [ ] Game statistics and history
- [ ] Replay system
- [ ] Custom game modes
- [ ] Web dashboard for game state

## Technical Objectives

### Code Quality
- Clean, readable Python code
- Comprehensive docstrings
- Type hints where appropriate
- Consistent naming conventions
- DRY principle (Don't Repeat Yourself)

### Architecture Principles
- **Separation of Concerns**: Game logic separate from Discord interface
- **Modularity**: Cogs for different command groups
- **Testability**: Pure functions for game logic (vote counting, state transitions)
- **Maintainability**: Clear project structure, well-documented code

### Performance
- Efficient message editing (batch updates)
- Minimal API calls to Discord
- Fast command response times
- Handle multiple concurrent games

### Security
- Input validation for all commands
- Permission checks for moderator actions
- Prevent vote manipulation
- Secure storage of Discord token in .env
- Rate limiting (future)

## Project Structure Philosophy

### Cogs (Command Groups)
- `game_management.py`: Game lifecycle commands (/new_game, /start)
- `player_actions.py`: Player interaction commands (/join, /vote)
- `moderator.py`: Admin/moderator commands (/end_day, future admin tools)

### Utils (Helper Functions)
- `database.py`: All file I/O operations for game state
- `game_logic.py`: Pure functions for vote counting, winner determination
- `permissions.py`: Permission checking helpers

### Models (Data Structures)
- `game.py`: Game class with state management
- `player.py`: Player class with vote tracking
- `role.py`: Role class hierarchy (for future)

## Development Priorities

1. **Get core loop working**: new_game → join → start → vote → end_day
2. **Polish user experience**: Clear messages, error handling, validation
3. **Add role system**: Start with simple roles (Vigilante template)
4. **Enhance features**: Settings, statistics, night actions
5. **Scale & optimize**: Database migration, performance improvements

## Success Criteria

### MVP Success (Phase 1)
- Users can create and join games
- Voting system works correctly
- Day cycles advance properly
- No data loss on bot restart
- All commands have proper error handling

### Long-term Success
- Multiple communities using the bot
- Support for 10+ concurrent games
- Role system fully functional
- Positive user feedback
- Active maintenance and feature requests

## Non-Goals (For Now)

- Web interface (future consideration)
- Voice channel integration
- Advanced statistics/ML analysis
- Mobile app
- Cross-server games

## Deployment Strategy

### Development
- Local testing in personal Discord server
- Test with 3-5 players minimum
- Validate all command flows

### Production
- Host on reliable platform (VPS, cloud)
- Environment-based configuration
- Logging for debugging
- Automated restarts on failure
- Backup of game state files

## User Experience Principles

1. **Clear Communication**: Bot messages should be informative and friendly
2. **Forgiving**: Allow users to correct mistakes (change votes, etc.)
3. **Transparent**: Game state visible to all players (via tracking messages)
4. **Fair**: Prevent cheating, ensure equal opportunity
5. **Fun**: Enhance the social deduction experience, don't get in the way

## Community & Support

- README.md with setup instructions
- Example .env file
- Clear error messages guide users to solutions
- Future: Wiki with game rules and strategies
- Future: Discord support server

## Maintenance Plan

- Regular updates for discord.py compatibility
- Bug fixes prioritized
- Feature requests evaluated
- Community feedback incorporated
- Documentation kept up-to-date

## License & Usage
- Open source (to be decided: MIT, GPL, etc.)
- Free to use and modify
- Attribution appreciated
- Community contributions welcome

---

## Quick Reference: Command Summary

| Command | Permission | Description |
|---------|-----------|-------------|
| `/new_game <name>` | Anyone | Create a new game |
| `/join` | Anyone | Join game during signup |
| `/start <name>` | Moderator/Creator | Start the game |
| `/vote <target>` | Players | Vote for elimination |
| `/end_day <name>` | Moderator/Creator | End current day |

## Quick Reference: Vote Options

- `@mention`: Vote to eliminate that player
- `Veto`: Don't participate in vote
- `Abstain`: Vote to eliminate nobody

## Project Philosophy

**Keep it simple, keep it fun, keep it Discord-native.**

The best bot is one that gets out of the way and lets players focus on the social deduction gameplay. All technical decisions should support this goal.
