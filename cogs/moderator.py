"""
Moderator Cog
Handles /end_day and other admin commands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from models.game import Game, GameStatus
from utils import database, permissions, game_logic


class Moderator(commands.Cog):
    """Cog for moderator actions."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="end_day", description="End the current day and tally votes (Moderator only)")
    @app_commands.describe(name="The name of the game")
    async def end_day(self, interaction: discord.Interaction, name: str):
        """End the current day, count votes, and advance to next day."""
        # Load game
        game = database.get_game(name)
        if not game:
            await interaction.response.send_message(
                f"❌ No game named '{name}' found!",
                ephemeral=True
            )
            return

        # Check permissions
        if not permissions.can_manage_game(interaction.user.id, interaction.user, game):
            await interaction.response.send_message(
                "❌ You don't have permission to manage this game!",
                ephemeral=True
            )
            return

        # Check if game is active
        if game.status != GameStatus.ACTIVE:
            await interaction.response.send_message(
                f"❌ Game '{name}' is not currently active!",
                ephemeral=True
            )
            return

        # Defer as this might take a moment
        await interaction.response.defer()

        try:
            current_day = game.current_day

            # Get votes from PlayerActions cog
            player_actions_cog = self.bot.get_cog('PlayerActions')
            votes = {}
            if player_actions_cog and name in player_actions_cog.votes:
                if current_day in player_actions_cog.votes[name]:
                    votes = player_actions_cog.votes[name][current_day]

            # Get alive players
            alive_players = game.get_alive_players()

            # Count votes
            eliminated_id, result_type, tally = game_logic.count_votes(votes, alive_players)

            # Get user names
            user_names = {}
            for player_id in game.players:
                try:
                    user = await self.bot.fetch_user(player_id)
                    user_names[player_id] = user.name
                except:
                    user_names[player_id] = f"User {player_id}"

            # Format end-of-day message
            announcement = game_logic.format_day_end_message(
                eliminated_id, result_type, tally, user_names, current_day
            )

            # Eliminate player if needed
            if eliminated_id:
                game.eliminate_player(eliminated_id)

            # Check win condition
            win_team = game_logic.check_win_condition(game.get_alive_players(), game.roles)
            if win_team:
                # Game over
                game.end_game()
                database.save_game(game)

                embed = discord.Embed(
                    title=f"🏁 {name} - Game Over!",
                    description=announcement + f"\n\n**The game has ended!**",
                    color=discord.Color.red()
                )

                await interaction.followup.send(embed=embed)

                # Post in game channels
                votes_channel_id = game.channels[current_day]["votes_channel_id"]
                discussion_channel_id = game.channels[current_day]["discussion_channel_id"]

                votes_channel = await self.bot.fetch_channel(votes_channel_id)
                discussion_channel = await self.bot.fetch_channel(discussion_channel_id)

                await votes_channel.send(embed=embed)
                await discussion_channel.send(embed=embed)

                return

            # Create next day channels
            next_day = current_day + 1
            guild = interaction.guild
            category_name = f"CSS Solaris: {name}"
            category = discord.utils.get(guild.categories, name=category_name)

            votes_channel = await guild.create_text_channel(
                f"{name}-day-{next_day}-votes",
                category=category,
                topic=f"Day {next_day} voting for {name}"
            )

            discussion_channel = await guild.create_text_channel(
                f"{name}-day-{next_day}-discussion",
                category=category,
                topic=f"Day {next_day} discussion for {name}"
            )

            # Create vote tracking message
            vote_embed = discord.Embed(
                title=f"📊 Day {next_day} Votes - {name}",
                description="No votes yet. Use `/vote @player` or `/vote Abstain` or `/vote Veto`",
                color=discord.Color.blue()
            )
            vote_message = await votes_channel.send(embed=vote_embed)

            # Update game state
            game.current_day = next_day
            game.channels[next_day] = {
                "votes_channel_id": votes_channel.id,
                "discussion_channel_id": discussion_channel.id,
                "votes_message_id": vote_message.id
            }
            database.save_game(game)

            # Archive old channels (set to read-only)
            old_votes_channel = await self.bot.fetch_channel(game.channels[current_day]["votes_channel_id"])
            old_discussion_channel = await self.bot.fetch_channel(game.channels[current_day]["discussion_channel_id"])

            await old_votes_channel.set_permissions(guild.default_role, send_messages=False)
            await old_discussion_channel.set_permissions(guild.default_role, send_messages=False)

            # Announce results
            alive_mentions = [f"<@{pid}>" for pid in game.get_alive_players()]

            result_embed = discord.Embed(
                title=f"🌙 Day {current_day} - Results",
                description=announcement,
                color=discord.Color.purple()
            )

            next_day_embed = discord.Embed(
                title=f"🌅 {name} - Day {next_day} Begins!",
                description=f"**Alive Players ({len(game.get_alive_players())}):**\n" + ", ".join(alive_mentions) + "\n\n"
                           f"**Channels:**\n"
                           f"🗳️ {votes_channel.mention} - Cast your votes here\n"
                           f"💬 {discussion_channel.mention} - Discuss here",
                color=discord.Color.gold()
            )

            await interaction.followup.send(embed=result_embed)
            await interaction.followup.send(embed=next_day_embed)

            await old_votes_channel.send(embed=result_embed)
            await old_discussion_channel.send(embed=result_embed)
            await votes_channel.send(embed=next_day_embed)
            await discussion_channel.send(embed=next_day_embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to end day: {e}")


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(Moderator(bot))
