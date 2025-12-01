"""
CSS Solaris Discord Bot
Main entry point for the bot.
"""

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')  # Optional: for faster command sync during development

if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN not found in environment variables!")

# Bot setup
intents = discord.Intents.default()
intents.members = True  # Required for fetching user info in votes/signups
intents.guilds = True  # Required for guild information like owner_id

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    """Called when bot is ready."""
    print('='*50)
    print(f'✅ {bot.user} has connected to Discord!')
    print(f'📊 Bot is in {len(bot.guilds)} guild(s)')

    for guild in bot.guilds:
        print(f'   - {guild.name} (ID: {guild.id})')

    # Sync commands
    try:
        if GUILD_ID:
            # Sync to specific guild for faster development
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f'✅ Synced commands to guild {GUILD_ID}')
        else:
            # Sync globally
            await bot.tree.sync()
            print('✅ Synced commands globally')
    except Exception as e:
        print(f'❌ Failed to sync commands: {e}')

    print(f'🚀 Bot is ready! Use /setup to get started.')
    print('='*50)


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        print(f'Error: {error}')
        await ctx.send(f'An error occurred: {error}')


async def load_cogs():
    """Load all cogs."""
    cogs = [
        'cogs.game_management',
        'cogs.player_actions',
        'cogs.moderator',
        'cogs.gm_commands'
    ]

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f'Loaded {cog}')
        except Exception as e:
            print(f'Failed to load {cog}: {e}')


async def main():
    """Main function to run the bot."""
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
