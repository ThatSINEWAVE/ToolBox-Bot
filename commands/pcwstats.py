import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json


class PCWStatsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.stats_url = "https://pcwstats-pixel-api.vercel.app/api/stats"
        self.pixel_config_url = "https://cdn.jsdelivr.net/gh/PCWStats/Website-Configs@main/tracking-pixel.json"
        self.pcwstats_url = "https://pcwstats.github.io/"
        self.cache: Dict[str, Any] = {
            "stats": None,
            "pixel_config": None,
            "last_updated": None,
        }

    async def fetch_data(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                logging.error(
                    f"Failed to fetch data from {url}: HTTP {response.status}"
                )
                return None
        except Exception as e:
            logging.error(f"Error fetching data from {url}: {e}")
            return None

    async def refresh_cache(self) -> None:
        try:
            stats = await self.fetch_data(self.stats_url)
            pixel_config = await self.fetch_data(self.pixel_config_url)

            if stats:
                self.cache["stats"] = stats
            if pixel_config:
                self.cache["pixel_config"] = pixel_config

            self.cache["last_updated"] = datetime.utcnow()
            logging.info("PCWStats cache refreshed")
        except Exception as e:
            logging.error(f"Error refreshing PCWStats cache: {e}")

    def get_page_name(self, pixel_filename: str) -> str:
        """Get the human-readable page name from the pixel filename"""
        if not self.cache["pixel_config"]:
            return pixel_filename

        for pixel in self.cache["pixel_config"].get("pixels", []):
            if pixel.get("pixel_filename") == pixel_filename:
                return pixel.get("page_name", pixel_filename)

        return pixel_filename

    def calculate_stats(
        self, stats_data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Calculate total views, 30-day views, and top pages"""
        if not stats_data:
            return None

        total_views = 0
        thirty_day_views = 0
        top_pages = []
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        for pixel_filename, data in stats_data.items():
            # Calculate total views
            pixel_total = data.get("totalViews", 0)
            total_views += pixel_total

            # Calculate 30-day views
            pixel_daily = data.get("dailyViews", {})
            pixel_thirty_day = 0
            for date_str, views in pixel_daily.items():
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    if date >= thirty_days_ago:
                        pixel_thirty_day += views
                except:
                    continue
            thirty_day_views += pixel_thirty_day

            # Prepare for top pages
            page_name = self.get_page_name(pixel_filename)
            top_pages.append(
                {
                    "name": page_name,
                    "total": pixel_total,
                    "recent": pixel_thirty_day,
                    "pixel": pixel_filename,
                }
            )

        # Sort by total views descending
        top_pages.sort(key=lambda x: x["total"], reverse=True)

        return {
            "total_views": total_views,
            "thirty_day_views": thirty_day_views,
            "top_pages": top_pages[:10],  # Only keep top 10
        }

    @app_commands.command(
        name="pcwstats",
        description="Get statistics about PCWStats website traffic",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def pcwstats(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        # Refresh cache if empty or stale (older than 1 hour)
        if (
            self.cache["last_updated"] is None
            or (datetime.utcnow() - self.cache["last_updated"]).total_seconds() > 3600
        ):
            await self.refresh_cache()

        # Initialize embed with clickable title to PCWStats
        embed = discord.Embed(
            title="📊 PCWStats Website Statistics", color=0x7289DA, url=self.pcwstats_url
        )

        # Check if cache is loaded
        if not self.cache["stats"] or not self.cache["pixel_config"]:
            embed.description = (
                "⚠️ PCWStats statistics not loaded. Please try again later."
            )
            await interaction.followup.send(embed=embed)
            return

        try:
            stats = self.calculate_stats(self.cache["stats"])

            if not stats:
                embed.description = "⚠️ Error calculating statistics."
                await interaction.followup.send(embed=embed)
                return

            # Add main statistics
            embed.add_field(
                name="📈 Overall Statistics",
                value=f"**Total Lifetime Views:** {stats['total_views']:,}\n"
                f"**Last 30 Days Views:** {stats['thirty_day_views']:,}",
                inline=False,
            )

            # Add top pages
            top_pages_text = []
            for i, page in enumerate(stats["top_pages"], 1):
                top_pages_text.append(
                    f"{i}. **{page['name']}** - {page['total']:,} views "
                    f"({page['recent']:,} recent)"
                )

            embed.add_field(
                name="🏆 Top 10 Pages",
                value="\n".join(top_pages_text) or "No data available",
                inline=False,
            )

            # Set footer with cache info
            if self.cache["last_updated"]:
                embed.set_footer(
                    text=f"PCWStats Database • Last updated: {self.cache['last_updated'].strftime('%Y-%m-%d %H:%M UTC')}"
                )
            else:
                embed.set_footer(text="PCWStats Database • Cache not loaded")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error(f"Error parsing PCWStats: {e}")
            embed.description = "⚠️ Error parsing PCWStats statistics."
            await interaction.followup.send(embed=embed)

    def cog_unload(self) -> None:
        asyncio.create_task(self.session.close())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PCWStatsCommands(bot))
