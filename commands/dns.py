import discord
from discord.ext import commands
from discord import app_commands
import dns.resolver
import dns.reversename
import logging
from urllib.parse import urlparse


class DNSCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.resolver = dns.resolver.Resolver()
        self.resolver.nameservers = ["1.1.1.1", "8.8.8.8"]  # Cloudflare and Google DNS

    async def query_dns(self, record_type, domain):
        try:
            answers = await asyncio.to_thread(
                self.resolver.resolve, domain, record_type
            )
            return [str(r) for r in answers]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return []
        except Exception as e:
            logging.error(f"DNS query error for {record_type} {domain}: {e}")
            return ["Error fetching record"]

    @app_commands.command(
        name="dns", description="Perform full DNS enumeration for a domain"
    )
    @app_commands.describe(domain="The domain to check DNS records for")
    async def dns(self, interaction: discord.Interaction, domain: str):
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

            # Query all record types in parallel
            record_types = [
                "A",
                "AAAA",
                "MX",
                "TXT",
                "NS",
                "CNAME",
                "SOA",
                "DMARC",
                "SPF",
            ]
            tasks = {rt: self.query_dns(rt, domain) for rt in record_types}

            # Special handling for DMARC and SPF
            tasks["DMARC"] = self.query_dns("TXT", f"_dmarc.{domain}")
            tasks["SPF"] = self.query_dns("TXT", domain)

            results = {}
            for rt, task in tasks.items():
                results[rt] = await task

            # Process SPF and DMARC from TXT records
            spf_records = [r for r in results["TXT"] if "v=spf1" in r]
            dmarc_records = results["DMARC"]

            # Build embed
            embed = discord.Embed(title=f"🔍 DNS Records for {domain}", color=0x3498DB)

            # Add fields for each record type
            for rt in ["A", "AAAA", "MX", "NS", "CNAME"]:
                if results[rt]:
                    embed.add_field(
                        name=rt, value="\n".join(results[rt][:5]), inline=True
                    )

            # Add TXT records (limited)
            if results["TXT"]:
                embed.add_field(
                    name="TXT",
                    value="\n".join(
                        [
                            r[:50] + "..." if len(r) > 50 else r
                            for r in results["TXT"][:3]
                        ]
                    ),
                    inline=False,
                )

            # Add security records
            security_fields = []
            if spf_records:
                security_fields.append(f"• **SPF**: ✅ Present")
            else:
                security_fields.append(f"• **SPF**: ❌ Missing")

            if dmarc_records:
                security_fields.append(f"• **DMARC**: ✅ Present")
            else:
                security_fields.append(f"• **DMARC**: ❌ Missing")

            embed.add_field(
                name="Email Security", value="\n".join(security_fields), inline=False
            )

            embed.set_footer(
                text=f"DNS queries performed using Cloudflare (1.1.1.1) and Google (8.8.8.8) resolvers"
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error(f"Error in DNS command: {e}")
            await interaction.followup.send(
                "An error occurred while fetching DNS records."
            )


async def setup(bot):
    await bot.add_cog(DNSCommand(bot))
