import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
from urllib.parse import urlparse
import logging


class HeadersCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def analyze_headers(self, headers):
        security_headers = [
            "Content-Security-Policy",
            "Strict-Transport-Security",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Feature-Policy",
            "Permissions-Policy",
        ]

        analysis = []
        score = 0
        max_score = len(security_headers)

        for header in security_headers:
            if header in headers:
                status = "✅ Present"
                score += 1
            else:
                status = "❌ Missing"

            analysis.append(f"• **{header}**: {status}")

        return analysis, score, max_score

    @app_commands.command(
        name="headers", description="Analyze HTTP security headers of a website"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL to check headers for")
    async def headers(self, interaction: discord.Interaction, url: str):
        try:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            parsed = urlparse(url)
            if not parsed.netloc:
                await interaction.response.send_message(
                    "Invalid URL format", ephemeral=True
                )
                return

            await interaction.response.defer()

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(url, timeout=10) as response:
                        headers = dict(response.headers)

                        analysis, score, max_score = self.analyze_headers(headers)
                        percentage = int((score / max_score) * 100)

                        embed = discord.Embed(
                            title=f"🔒 Security Headers Analysis for {parsed.netloc}",
                            description=f"**Security Score**: {score}/{max_score} ({percentage}%)",
                            color=0x00FF00
                            if percentage > 75
                            else (0xFFA500 if percentage > 50 else 0xFF0000),
                        )

                        embed.add_field(
                            name="Header Analysis",
                            value="\n".join(analysis),
                            inline=False,
                        )

                        embed.add_field(
                            name="Additional Info",
                            value=f"• **Server**: {headers.get('Server', 'Not disclosed')}\n"
                            f"• **Content-Type**: {headers.get('Content-Type', 'Unknown')}",
                            inline=False,
                        )

                        embed.set_footer(
                            text="✅ = Good security practice | ❌ = Missing security header"
                        )

                        await interaction.followup.send(embed=embed)

                except asyncio.TimeoutError:
                    await interaction.followup.send(
                        "Request timed out. The server might be slow or blocking our requests."
                    )
                except Exception as e:
                    await interaction.followup.send(
                        f"Failed to fetch headers: {str(e)}"
                    )

        except Exception as e:
            logging.error(f"Error in headers command: {e}")
            await interaction.followup.send("An unexpected error occurred.")


async def setup(bot):
    await bot.add_cog(HeadersCommand(bot))
