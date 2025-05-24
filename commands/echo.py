import discord
from discord import app_commands
from discord.ext import commands
import logging


class EchoCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="echo",
        description="Create a custom embed message"
    )
    @app_commands.describe(
        title="The title of the embed",
        paragraph1="First paragraph content (optional)",
        paragraph2="Second paragraph content (optional)",
        paragraph3="Third paragraph content (optional)",
        footer="Footer text (optional)",
        color="Embed color in hex (e.g. #FF5733, optional)"
    )
    async def echo(
            self,
            interaction: discord.Interaction,
            title: str,
            paragraph1: str = None,
            paragraph2: str = None,
            paragraph3: str = None,
            footer: str = None,
            color: str = None
    ):
        try:
            # Default to pure red (#FF0000) if no color is specified
            embed_color = discord.Color.from_str("#FF0000")

            # Override with user's color if provided
            if color:
                try:
                    # Remove # if present and convert to integer
                    color_hex = color.lstrip('#')
                    if len(color_hex) == 6:
                        embed_color = discord.Color(int(color_hex, 16))
                except ValueError:
                    await interaction.response.send_message(
                        "Invalid color format. Using default red color.",
                        ephemeral=True
                    )

            # Create embed
            embed = discord.Embed(
                title=title,
                color=embed_color
            )

            # Add paragraphs if they exist
            if paragraph1:
                embed.add_field(
                    name="\u200b",  # Zero-width space for nameless field
                    value=paragraph1,
                    inline=False
                )

            if paragraph2:
                embed.add_field(
                    name="\u200b",
                    value=paragraph2,
                    inline=False
                )

            if paragraph3:
                embed.add_field(
                    name="\u200b",
                    value=paragraph3,
                    inline=False
                )

            # Add footer if exists
            if footer:
                embed.set_footer(text=footer)

            # Send the embed
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logging.error(f"Error in echo command: {e}")
            await interaction.response.send_message(
                "An error occurred while creating the embed.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(EchoCommand(bot))