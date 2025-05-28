import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
import os


class IPCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ipinfo_token = os.getenv("IPINFO_API_TOKEN")

    @app_commands.command(
        name="ip", description="Get geolocation and network info for an IP address"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ip="The IP address to lookup")
    async def ip(self, interaction: discord.Interaction, ip: str):
        try:
            if not self.ipinfo_token:
                await interaction.response.send_message(
                    "IPInfo API is not configured.", ephemeral=True
                )
                return

            await interaction.response.defer()

            async with aiohttp.ClientSession() as session:
                try:
                    # Get IP info
                    async with session.get(
                        f"https://ipinfo.io/{ip}?token={self.ipinfo_token}"
                    ) as response:
                        if response.status == 200:
                            data = await response.json()

                            embed = discord.Embed(
                                title=f"🌍 IP Information for {ip}", color=0x3498DB
                            )

                            # Basic info
                            embed.add_field(
                                name="Location",
                                value=f"• **Country**: {data.get('country', 'Unknown')}\n"
                                f"• **Region**: {data.get('region', 'Unknown')}\n"
                                f"• **City**: {data.get('city', 'Unknown')}\n"
                                f"• **Postal Code**: {data.get('postal', 'Unknown')}",
                                inline=True,
                            )

                            # Network info
                            embed.add_field(
                                name="Network",
                                value=f"• **Hostname**: {data.get('hostname', 'Unknown')}\n"
                                f"• **ASN**: {data.get('asn', {}).get('asn', 'Unknown')}\n"
                                f"• **ISP**: {data.get('org', 'Unknown').split('AS')[0].strip() if 'org' in data else 'Unknown'}",
                                inline=True,
                            )

                            # Privacy info
                            privacy_info = []
                            if data.get("privacy", {}).get("proxy", False):
                                privacy_info.append("• **Proxy/VPN**: ✅ Likely")
                            if data.get("privacy", {}).get("hosting", False):
                                privacy_info.append("• **Hosting/DC**: ✅ Likely")
                            if data.get("privacy", {}).get("tor", False):
                                privacy_info.append("• **Tor Node**: ✅ Likely")

                            if privacy_info:
                                embed.add_field(
                                    name="Privacy",
                                    value="\n".join(privacy_info),
                                    inline=False,
                                )

                            # Map if available
                            if "loc" in data:
                                lat, lon = data["loc"].split(",")
                                embed.set_image(
                                    url=f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lon}&zoom=10&size=600x300&maptype=roadmap&markers=color:red%7C{lat},{lon}&key=AIzaSyDummyKey"
                                )

                            embed.set_footer(text="Data provided by ipinfo.io")

                            await interaction.followup.send(embed=embed)
                        else:
                            await interaction.followup.send(
                                f"Failed to fetch IP info: HTTP {response.status}"
                            )

                except Exception as e:
                    await interaction.followup.send(f"Error during IP lookup: {str(e)}")

        except Exception as e:
            logging.error(f"Error in IP command: {e}")
            await interaction.followup.send("An unexpected error occurred.")


async def setup(bot):
    await bot.add_cog(IPCommand(bot))
