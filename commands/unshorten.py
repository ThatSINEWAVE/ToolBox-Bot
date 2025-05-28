import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from urllib.parse import urlparse


class UnshortenCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def unshorten_url(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                # Use a free unshortening service
                async with session.get(
                    f"http://x.datasig.io/shorturl?url={url}", timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("resolved_url", url)
                    return url
        except:
            return url

    async def follow_redirects(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True) as response:
                    return str(response.url)
        except:
            return url

    @app_commands.command(
        name="unshorten", description="Follow URL redirects to reveal final destination"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The shortened URL to unshorten")
    async def unshorten(self, interaction: discord.Interaction, url: str):
        try:
            if not url.startswith(("http://", "https://")):
                url = f"http://{url}"

            parsed = urlparse(url)
            if not parsed.netloc:
                await interaction.response.send_message(
                    "Invalid URL format", ephemeral=True
                )
                return

            await interaction.response.defer()

            # First try API, then fallback to manual redirect following
            final_url = await self.unshorten_url(url)
            if final_url == url:
                final_url = await self.follow_redirects(url)

            embed = discord.Embed(title="🔗 URL Unshortener", color=0x3498DB)

            embed.add_field(name="Original URL", value=f"[{url}]({url})", inline=False)

            embed.add_field(
                name="Final Destination",
                value=f"[{final_url}]({final_url})",
                inline=False,
            )

            # Security warning if domains don't match
            original_domain = urlparse(url).netloc.replace("www.", "")
            final_domain = urlparse(final_url).netloc.replace("www.", "")

            if original_domain != final_domain:
                embed.add_field(
                    name="⚠️ Security Warning",
                    value="The final domain does not match the original short URL domain!",
                    inline=False,
                )
                embed.color = 0xFF0000

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error(f"Error in unshorten command: {e}")
            await interaction.followup.send(
                "An error occurred while unshortening the URL."
            )


async def setup(bot):
    await bot.add_cog(UnshortenCommand(bot))
