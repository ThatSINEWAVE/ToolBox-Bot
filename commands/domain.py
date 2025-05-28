import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
import dns.resolver
from urllib.parse import urlparse


class DomainCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.resolver = dns.resolver.Resolver()
        self.resolver.nameservers = ["1.1.1.1", "8.8.8.8"]

    async def get_whois(self, domain):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://www.whois.com/whois/{domain}"
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Extract relevant whois info (simplified)
                        return text[:2000]  # Limit to first 2000 chars
                    return "WHOIS lookup failed"
        except:
            return "WHOIS lookup error"

    async def get_subdomains(self, domain):
        try:
            # Use crt.sh certificate transparency logs
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://crt.sh/?q=%.{domain}&output=json"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        subdomains = set()
                        for cert in data:
                            name = cert.get("name_value", "")
                            if name and domain in name:
                                subdomains.update(name.split("\n"))
                        return sorted(subdomains)[:10]  # Return top 10
                    return []
        except:
            return []

    @app_commands.command(
        name="domain", description="Perform full domain reconnaissance"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(domain="The domain to investigate")
    async def domain(self, interaction: discord.Interaction, domain: str):
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

            # Run all checks in parallel
            whois_task = asyncio.create_task(self.get_whois(domain))
            subdomains_task = asyncio.create_task(self.get_subdomains(domain))

            # DNS records
            dns_records = {}
            record_types = ["A", "AAAA", "MX", "NS", "TXT"]
            for rt in record_types:
                try:
                    answers = await asyncio.to_thread(self.resolver.resolve, domain, rt)
                    dns_records[rt] = [str(r) for r in answers]
                except:
                    dns_records[rt] = []

            # Get results from async tasks
            whois_info = await whois_task
            subdomains = await subdomains_task

            # Build embed
            embed = discord.Embed(title=f"🔍 Domain Recon: {domain}", color=0x3498DB)

            # WHOIS info
            embed.add_field(
                name="WHOIS Info",
                value=f"```{whois_info[:1000]}```"
                if whois_info
                else "No WHOIS data found",
                inline=False,
            )

            # DNS records
            dns_text = []
            for rt, records in dns_records.items():
                if records:
                    dns_text.append(
                        f"• **{rt}**: {', '.join(records[:3])}{'...' if len(records) > 3 else ''}"
                    )

            if dns_text:
                embed.add_field(
                    name="DNS Records", value="\n".join(dns_text), inline=False
                )

            # Subdomains
            if subdomains:
                embed.add_field(
                    name=f"Subdomains ({len(subdomains)})",
                    value="\n".join(f"• {s}" for s in subdomains),
                    inline=False,
                )

            # Security recommendations
            security_checks = []
            if not any("v=spf1" in r for r in dns_records.get("TXT", [])):
                security_checks.append("❌ No SPF record found")
            if not any("_dmarc." in s for s in subdomains):
                security_checks.append("❌ No DMARC record found")

            if security_checks:
                embed.add_field(
                    name="Security Recommendations",
                    value="\n".join(security_checks),
                    inline=False,
                )

            embed.set_footer(text="Domain reconnaissance results may be incomplete")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error(f"Error in domain command: {e}")
            await interaction.followup.send("An unexpected error occurred.")


async def setup(bot):
    await bot.add_cog(DomainCommand(bot))
