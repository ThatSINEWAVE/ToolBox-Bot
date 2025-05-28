import discord
from discord.ext import commands
from discord import app_commands
import ssl
import socket
import asyncio
import logging
from datetime import datetime
from urllib.parse import urlparse


class SSLCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_ssl(self, domain):
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443)) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

                # Parse certificate info
                issuer = dict(x[0] for x in cert["issuer"])
                subject = dict(x[0] for x in cert["subject"])
                valid_from = datetime.strptime(
                    cert["notBefore"], "%b %d %H:%M:%S %Y %Z"
                )
                valid_to = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                remaining_days = (valid_to - datetime.now()).days

                # Check for vulnerabilities
                protocol = ssock.version()
                cipher = ssock.cipher()

                return {
                    "domain": domain,
                    "subject": subject,
                    "issuer": issuer,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "remaining_days": remaining_days,
                    "protocol": protocol,
                    "cipher": cipher,
                    "is_valid": remaining_days > 0,
                }

    @app_commands.command(
        name="ssl", description="Check SSL/TLS configuration of a domain"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(domain="The domain to check SSL for")
    async def ssl(self, interaction: discord.Interaction, domain: str):
        try:
            # Clean domain input
            domain = (
                domain.lower()
                .replace("http://", "")
                .replace("https://", "")
                .replace("www.", "")
                .split("/")[0]
            )

            await interaction.response.defer()

            try:
                result = await self.check_ssl(domain)

                embed = discord.Embed(
                    title=f"🔐 SSL/TLS Certificate for {domain}",
                    color=0x00FF00 if result["is_valid"] else 0xFF0000,
                )

                # Certificate info
                embed.add_field(
                    name="Certificate Info",
                    value=f"• **Subject**: {result['subject'].get('commonName', 'Unknown')}\n"
                    f"• **Issuer**: {result['issuer'].get('organizationName', 'Unknown')}\n"
                    f"• **Valid From**: {result['valid_from'].strftime('%Y-%m-%d')}\n"
                    f"• **Valid To**: {result['valid_to'].strftime('%Y-%m-%d')}\n"
                    f"• **Days Remaining**: {result['remaining_days']}",
                    inline=False,
                )

                # Connection info
                embed.add_field(
                    name="Connection Details",
                    value=f"• **Protocol**: {result['protocol']}\n"
                    f"• **Cipher**: {result['cipher'][0]}\n"
                    f"• **Key Size**: {result['cipher'][2]} bits",
                    inline=False,
                )

                # Recommendations
                recommendations = []
                if "TLSv1" in result["protocol"]:
                    recommendations.append("❌ Upgrade from TLS 1.0/1.1 (deprecated)")
                if result["remaining_days"] < 30:
                    recommendations.append(
                        f"⚠️ Certificate expires soon ({result['remaining_days']} days)"
                    )
                if result["cipher"][2] < 128:
                    recommendations.append("⚠️ Weak cipher (consider upgrading)")

                if recommendations:
                    embed.add_field(
                        name="Recommendations",
                        value="\n".join(recommendations),
                        inline=False,
                    )

                await interaction.followup.send(embed=embed)

            except ssl.SSLError as e:
                await interaction.followup.send(f"SSL error: {str(e)}")
            except socket.gaierror:
                await interaction.followup.send("Could not resolve domain name")
            except Exception as e:
                await interaction.followup.send(f"Error checking SSL: {str(e)}")

        except Exception as e:
            logging.error(f"Error in SSL command: {e}")
            await interaction.followup.send("An unexpected error occurred.")


async def setup(bot):
    await bot.add_cog(SSLCommand(bot))
