import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
import base64
import io


POSTER_TEMPLATE = """Generate a vertical 1930s WPA-style propaganda poster. The aesthetic must be retro-futuristic and space-themed, mimicking traditional silkscreen printing with flat, bold colors, stark contrasts, dramatic geometric compositions, and a slightly distressed, vintage paper texture. Incorporate bold, blocky, vintage sans-serif typography.

Main Scene & Characters: {description}
{top_text_line}
{bottom_text_line}"""


class ImageCommands(commands.Cog):
    """Cog for AI image generation commands"""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

    @app_commands.command(name="poster", description="Generate a retro-futuristic WPA space propaganda poster")
    @app_commands.describe(
        description="The central scene — characters, actions, background elements",
        top_text="Optional text at the top of the poster",
        bottom_text="Optional text at the bottom of the poster"
    )
    async def generate_poster(self, interaction: discord.Interaction, description: str,
                              top_text: str = None, bottom_text: str = None):
        """Generate a WPA-style space propaganda poster from a description"""

        await interaction.response.defer()

        if not self.api_key:
            await interaction.followup.send(
                "❌ Gemini API key not configured. Please add GEMINI_API_KEY to the .env file.",
                ephemeral=True
            )
            return

        try:
            # Build prompt from template
            top_line = f"Top Text: {top_text}" if top_text else ""
            bottom_line = f"Bottom Text: {bottom_text}" if bottom_text else ""

            full_prompt = POSTER_TEMPLATE.format(
                description=description,
                top_text_line=top_line,
                bottom_text_line=bottom_line
            ).strip()

            image_data = await self._generate_image_from_gemini(full_prompt)

            image_bytes = base64.b64decode(image_data)
            image_file = discord.File(fp=io.BytesIO(image_bytes), filename="poster.png")

            embed = discord.Embed(
                title="🚀 WPA Space Poster",
                color=discord.Color.dark_gold()
            )
            embed.add_field(name="Scene", value=description, inline=False)
            if top_text:
                embed.add_field(name="Top Text", value=top_text, inline=True)
            if bottom_text:
                embed.add_field(name="Bottom Text", value=bottom_text, inline=True)

            await interaction.followup.send(embed=embed, file=image_file)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to generate poster: {str(e)}\n\n"
                "Make sure your Gemini API key is valid and has image generation enabled.",
                ephemeral=True
            )

    async def _generate_image_from_gemini(self, prompt: str) -> str:
        """
        Call Gemini 2.0 Flash to generate an image.
        Returns base64-encoded image data.
        """
        headers = {"Content-Type": "application/json"}

        payload = {
            "contents": [
                {"parts": [{"text": f"Generate an image: {prompt}"}]}
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
                "responseMimeType": "application/json"
            }
        }

        url = f"{self.api_url}?key={self.api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                return part["inlineData"]["data"]
                    raise Exception("No image generated in response")
                else:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")


async def setup(bot):
    await bot.add_cog(ImageCommands(bot))
