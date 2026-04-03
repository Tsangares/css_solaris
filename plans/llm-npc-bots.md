# LLM-Powered NPC Bots

## Idea
Create 4 separate Discord bot applications that act as NPC players in CSS Solaris games. Each has its own identity, avatar, and personality - and is driven by an LLM to behave like a human player.

## Architecture

### Discord Side
- 4 separate Discord applications (each with their own bot token, name, avatar)
- Each NPC bot joins the server as a real-looking user
- They can be @mentioned, they post messages as themselves, they react
- Main CSS Solaris bot orchestrates them via an internal API or shared database

### LLM Side
- Each NPC has a persona/system prompt defining their personality and playstyle
- LLM receives game context: current day, who's alive, vote history, recent discussion messages
- LLM decides: what to say in discussion, who to vote for, how to react
- Could use Claude API, Gemini, or any LLM provider
- MCP server could expose game state tools to the LLM (read_players, read_votes, cast_vote, send_message)

### NPC Personas (examples)
1. **Detective Dan** - analytical, always asking questions, tries to find inconsistencies
2. **Nervous Nelly** - paranoid, changes votes frequently, easily swayed
3. **Silent Sam** - rarely speaks, votes decisively, hard to read
4. **Social Sally** - chatty, builds alliances, tries to organize group votes

### Flow
1. Game starts, NPC bots are added as players
2. Each "turn" (or on a timer), the main bot sends game state to each NPC's LLM
3. LLM returns actions: messages to post, votes to cast
4. NPC bot posts/votes as itself in the Discord channels
5. When eliminated, NPC stops participating

### MCP Tools for NPC LLM
- `get_game_state` - current day, alive players, vote tally
- `get_recent_messages` - last N messages from discussion thread
- `send_message` - post in discussion as the NPC
- `cast_vote` - vote for a player
- `get_my_role` - check if crew or saboteur (affects strategy)

### Technical Considerations
- Rate limiting: don't spam, add delays to feel human
- Token costs: keep context window small, summarize history
- Saboteur strategy: LLM needs to coordinate with other saboteur NPCs without outing them
- Natural language: vary response length, use casual tone, make typos occasionally?
- Each NPC bot runs as a lightweight process/service alongside the main bot

### Implementation Steps
1. Create 4 Discord applications in the developer portal
2. Store their tokens in `.env` (NPC_BOT_TOKEN_1, etc.)
3. Build a lightweight NPC bot runner that connects each bot to Discord
4. Build an MCP server or simple API that exposes game state
5. Integrate LLM (Claude API) with persona prompts
6. Add orchestration in main bot: trigger NPC actions after events (day start, vote cast, etc.)
7. Add configurable delay/frequency settings

### Cost Estimate
- Claude Haiku for NPCs: ~$0.001-0.01 per NPC action
- 4 NPCs, ~10 actions per day, ~3 days per game = ~$0.12-1.20 per game
- Very cheap for fun factor

### Future Ideas
- NPCs that learn from past games
- Difficulty settings (how good the NPC is at deduction)
- NPC-only games for testing
- Webhook fallback (no separate apps needed, but can't be @mentioned)
