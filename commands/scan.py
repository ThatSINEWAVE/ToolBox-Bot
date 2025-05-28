import discord
from discord.ext import commands
from discord import app_commands
import shodan
import asyncio
import logging
import os


class ScanCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("SHODAN_API_TOKEN")
        self.api = shodan.Shodan(self.api_key) if self.api_key else None

    @app_commands.command(
        name="scan", description="Perform a quick port scan on an IP address"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ip="The IP address to scan")
    async def scan(self, interaction: discord.Interaction, ip: str):
        try:
            if not self.api:
                await interaction.response.send_message(
                    "Shodan API is not configured.", ephemeral=True
                )
                return

            await interaction.response.defer()

            try:
                # Use Shodan's free API for host information
                host = await asyncio.to_thread(self.api.host, ip)

                embed = discord.Embed(title=f"🔍 Scan Results for {ip}", color=0x3498DB)

                # Basic info
                embed.add_field(
                    name="General Info",
                    value=f"• **Country**: {host.get('country_name', 'Unknown')}\n"
                    f"• **Organization**: {host.get('org', 'Unknown')}\n"
                    f"• **Operating System**: {host.get('os', 'Unknown')}",
                    inline=False,
                )

                # Open ports (limit to 5 for embed)
                ports = host.get("ports", [])[:5]
                if ports:
                    port_info = []
                    for port in ports:
                        service = next(
                            (
                                item
                                for item in host.get("data", [])
                                if item["port"] == port
                            ),
                            None,
                        )
                        service_name = (
                            service.get("product", "Unknown") if service else "Unknown"
                        )
                        port_info.append(f"• **{port}**: {service_name}")

                    embed.add_field(
                        name="Open Ports (Top 5)",
                        value="\n".join(port_info),
                        inline=False,
                    )

                # Vulnerabilities
                vulns = host.get("vulns", [])
                if vulns:
                    embed.add_field(
                        name="⚠️ Vulnerabilities",
                        value=f"{len(vulns)} known vulnerabilities detected",
                        inline=False,
                    )
                    embed.color = 0xFF0000

                embed.set_footer(
                    text="Powered by Shodan.io - Results may be limited by API tier"
                )

                await interaction.followup.send(embed=embed)

            except shodan.APIError as e:
                await interaction.followup.send(f"Shodan API error: {str(e)}")
            except Exception as e:
                await interaction.followup.send(f"Error during scan: {str(e)}")

        except Exception as e:
            logging.error(f"Error in scan command: {e}")
            await interaction.followup.send("An unexpected error occurred.")


async def setup(bot):
    await bot.add_cog(ScanCommand(bot))
