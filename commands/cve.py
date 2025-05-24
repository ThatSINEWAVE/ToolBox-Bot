import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging


class CVECommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def fetch_cve_data(self, cve_id):
        try:
            async with self.session.get(
                f"https://cve.circl.lu/api/cve/{cve_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if data else {"error": "Empty response from API"}
                elif response.status == 404:
                    return {"error": "CVE not found"}
                return {"error": f"API returned status {response.status}"}
        except Exception as e:
            logging.error(f"CVE API error: {e}")
            return {"error": str(e)}

    @app_commands.command(
        name="cve", description="Get details about a CVE vulnerability"
    )
    @app_commands.describe(cve_id="The CVE ID to lookup (e.g., CVE-2021-44228)")
    async def cve(self, interaction: discord.Interaction, cve_id: str):
        try:
            # Validate CVE ID format
            cve_id = cve_id.upper()
            if not cve_id.startswith("CVE-") or len(cve_id.split("-")) != 3:
                await interaction.response.send_message(
                    "Please provide a valid CVE ID in format CVE-YYYY-NNNN",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            data = await self.fetch_cve_data(cve_id)

            if not data or "error" in data:
                error_msg = (
                    data.get("error", "No data returned from API")
                    if data
                    else "No data returned from API"
                )
                await interaction.followup.send(
                    f"❌ Could not fetch CVE data: {error_msg}", ephemeral=True
                )
                return

            # Build embed
            embed = discord.Embed(
                title=f"⚠️ {cve_id}",
                url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                color=0xED1C24,  # Red color for vulnerabilities
            )

            # Safely extract and add information
            summary = data.get("summary")
            if summary:
                embed.add_field(
                    name="Summary", value=summary[:1000], inline=False  # Limit length
                )

            # CVSS information
            cvss = data.get("cvss", {})
            cvss_fields = []
            if cvss.get("score"):
                cvss_fields.append(f"**Score**: {cvss['score']}")
            if cvss.get("severity"):
                cvss_fields.append(f"**Severity**: {cvss['severity'].title()}")
            if cvss.get("vector"):
                cvss_fields.append(f"**Vector**: `{cvss['vector']}`")

            if cvss_fields:
                embed.add_field(
                    name="CVSS Metrics", value="\n".join(cvss_fields), inline=False
                )

            # Affected products
            affected = data.get("vulnerable_product", [])
            if affected and isinstance(affected, list):
                embed.add_field(
                    name=f"Affected Products ({len(affected)})",
                    value="\n".join(f"• {p}" for p in affected[:3])
                    + ("\n..." if len(affected) > 3 else ""),
                    inline=False,
                )

            # References
            references = data.get("references", [])
            if references and isinstance(references, list):
                ref_links = "\n".join(f"• [Link]({ref})" for ref in references[:3])
                embed.add_field(name="References", value=ref_links, inline=False)

            # Exploit information
            exploit = "Yes" if data.get("exploit") else "No"
            embed.add_field(name="Exploit Available", value=exploit, inline=True)

            # Add last modified date if available
            if "Modified" in data:
                embed.add_field(
                    name="Last Modified", value=data["Modified"], inline=True
                )

            embed.set_footer(text="Data provided by CIRCL's CVE database and NVD")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error(f"Error in CVE command: {e}", exc_info=True)
            await interaction.followup.send(
                "An unexpected error occurred while processing the CVE request.",
                ephemeral=True,
            )

    def cog_unload(self):
        asyncio.create_task(self.session.close())


async def setup(bot):
    await bot.add_cog(CVECommand(bot))
