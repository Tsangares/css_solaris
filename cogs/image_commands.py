import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
import base64
import io


class ImageCommands(commands.Cog):
    """Cog for AI image generation commands"""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

    @app_commands.command(name="poster", description="Generate a WPA National Park space style propaganda poster")
    @app_commands.describe(description="Description of what the poster should depict")
    async def generate_poster(self, interaction: discord.Interaction, description: str):
        """Generate a WPA-style space propaganda poster from a description"""

        # Defer response since image generation may take time
        await interaction.response.defer()

        # Check if API key is configured
        if not self.api_key:
            await interaction.followup.send(
                "❌ Gemini API key not configured. Please add GEMINI_API_KEY to the .env file."
            )
            return

        try:
            # Construct the full prompt with the WPA style prefix
            full_prompt = f"WPA National Park space style propoganda poster {description}"

            # Call Gemini API to generate the image
            image_data = await self._generate_image_from_gemini(full_prompt)

            # Convert base64 image data to Discord file
            image_bytes = base64.b64decode(image_data)
            image_file = discord.File(
                fp=io.BytesIO(image_bytes),
                filename="poster.png"
            )

            # Create embed with prompt information
            embed = discord.Embed(
                title="🚀 WPA Space Poster Generated",
                description=f"**Description:** {description}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Generated with Gemini Imagen")

            # Send the image
            await interaction.followup.send(embed=embed, file=image_file)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to generate poster: {str(e)}\n\n"
                "Make sure your Gemini API key is valid and has image generation enabled.",
                ephemeral=True
            )

    async def _generate_image_from_gemini(self, prompt: str) -> str:
        """
        Call Gemini 2.0 Flash to generate an image from a text prompt.
        Returns base64-encoded image data.
        """
        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"Generate an image: {prompt}"}
                    ]
                }
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

                    # Extract image from Gemini 2.0 response
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
    """Setup function to load the cog"""
    await bot.add_cog(ImageCommands(bot))
