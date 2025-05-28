import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from urllib.parse import urlparse
from datetime import datetime
import json
from typing import Optional
import re


class DARTCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.compromised_accounts_url = "https://raw.githubusercontent.com/TheDARTProject/Database-Files/refs/heads/main/Main-Database/Compromised-Discord-Accounts.json"
        self.discord_servers_url = "https://raw.githubusercontent.com/TheDARTProject/Database-Files/refs/heads/main/Filter-Database/Discord-Servers.json"
        self.global_domains_url = "https://raw.githubusercontent.com/TheDARTProject/Database-Files/refs/heads/main/Filter-Database/Global-Domains.json"
        self.discord_ids_url = "https://raw.githubusercontent.com/TheDARTProject/Database-Files/refs/heads/main/Filter-Database/Discord-IDs.json"
        self.stats_url = "https://raw.githubusercontent.com/TheDARTProject/Database-Files/refs/heads/main/Inspection-Database/Inspection.md"
        self.cache = {
            "compromised_accounts": None,
            "discord_servers": None,
            "global_domains": None,
            "discord_ids": None,
            "stats": None,
            "last_updated": None,
        }
        self.dart_project_url = "https://thedartproject.github.io/"

    async def fetch_data(self, url):
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    # Try to parse the response as JSON regardless of content-type
                    text = await response.text()
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text  # Return raw text if not JSON
                logging.error(
                    f"Failed to fetch data from {url}: HTTP {response.status}"
                )
                return None
        except Exception as e:
            logging.error(f"Error fetching data from {url}: {e}")
            return None

    async def refresh_cache(self):
        try:
            compromised_accounts = await self.fetch_data(self.compromised_accounts_url)
            discord_servers = await self.fetch_data(self.discord_servers_url)
            global_domains = await self.fetch_data(self.global_domains_url)
            discord_ids = await self.fetch_data(self.discord_ids_url)
            stats = await self.fetch_data(self.stats_url)

            if compromised_accounts:
                self.cache["compromised_accounts"] = compromised_accounts
            if discord_servers:
                self.cache["discord_servers"] = discord_servers
            if global_domains:
                self.cache["global_domains"] = global_domains
            if discord_ids:
                self.cache["discord_ids"] = discord_ids
            if stats:
                self.cache["stats"] = stats

            self.cache["last_updated"] = datetime.utcnow()
            logging.info("DART Project Database cache refreshed")
        except Exception as e:
            logging.error(f"Error refreshing DART Project cache: {e}")

    def is_discord_url(self, url):
        parsed = urlparse(url)
        return parsed.netloc in ["discord.com", "discord.gg"]

    def extract_domain(self, url):
        parsed = urlparse(url)
        return parsed.netloc

    def extract_invite_code(self, url):
        """Extract invite code from Discord invite URL"""
        if not self.is_discord_url(url):
            return None

        # Handle both discord.com/invite/CODE and discord.gg/CODE formats
        if "discord.com/invite/" in url:
            return url.split("discord.com/invite/")[-1].split("?")[0].split("#")[0]
        elif "discord.gg/" in url:
            return url.split("discord.gg/")[-1].split("?")[0].split("#")[0]

        return None

    def format_timestamp(self, timestamp):
        """Convert Unix timestamp to readable date format"""
        try:
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
            return str(timestamp)
        except:
            return str(timestamp)

    def format_embed_field(self, data: dict, exclude_keys: list = None) -> str:
        if exclude_keys is None:
            exclude_keys = []

        formatted = []
        for key, value in data.items():
            if key in exclude_keys:
                continue

            # Special handling for timestamp fields
            if key in ["FOUND_ON", "SERVER_STATUS_CHANGE", "INVITE_STATUS_CHANGE"] and isinstance(value, (int, float)):
                if value != "UNKNOWN" and str(value) != "UNKNOWN":
                    formatted.append(f"**{key}:** {self.format_timestamp(value)}")
                else:
                    formatted.append(f"**{key}:** {str(value)}")
            elif isinstance(value, dict):
                formatted.append(f"**{key}:**")
                formatted.append(self.format_embed_field(value, exclude_keys))
            elif isinstance(value, list):
                formatted.append(f"**{key}:**")
                for i, item in enumerate(value, 1):
                    if isinstance(item, dict):
                        formatted.append(
                            f"{i}. {self.format_embed_field(item, exclude_keys)}"
                        )
                    else:
                        formatted.append(f"{i}. {str(item)}")
            else:
                formatted.append(f"**{key}:** {str(value)}")

        return "\n".join(formatted)

    def parse_stats(self, stats_text):
        stats = {}

        # Extract main stats
        if "## Total Cases: " in stats_text:
            stats["Total Cases"] = stats_text.split("## Total Cases: ")[1].split("\n")[
                0
            ]
        if "## Protected Members: " in stats_text:
            stats["Protected Members"] = stats_text.split("## Protected Members: ")[
                1
            ].split("\n")[0]

        # Count other categories
        sections = {
            "Found On Server": "Servers",
            "Account Status": "Account Statuses",
            "Account Type": "Account Types",
            "Behaviour": "Behaviors",
            "Attack Method": "Attack Methods",
            "Attack Vector": "Attack Vectors",
            "Attack Goal": "Attack Goals",
            "Attack Surface": "Attack Surfaces",
            "Suspected Region Of Origin": "Countries",
            "Final Url Status": "Final URL Statuses",
            "Surface Url Status": "Surface URL Statuses",
        }

        for section, name in sections.items():
            if f"## {section}" in stats_text:
                start = stats_text.find(f"## {section}") + len(f"## {section}") + 1
                end = (
                    stats_text.find("##", start)
                    if stats_text.find("##", start) != -1
                    else len(stats_text)
                )
                content = stats_text[start:end].strip()
                items = [
                    line[2:] for line in content.split("\n") if line.startswith("- ")
                ]
                stats[name] = str(len(items))

        # Extract additional entries
        if "## Additional Entries" in stats_text:
            start = (
                    stats_text.find("## Additional Entries")
                    + len("## Additional Entries")
                    + 1
            )
            content = stats_text[start:].strip()
            for line in content.split("\n"):
                if "**" in line and ": " in line:
                    try:
                        key = line.split("**")[1]
                        value = line.split(": ")[1].split(" ")[0]
                        stats[key] = value
                    except IndexError:
                        continue

        return stats

    def check_domain_in_list(self, domain, domain_list):
        """Check if domain matches any entry in the global domains list"""
        if not isinstance(domain_list, list):
            return None

        for entry in domain_list:
            if isinstance(entry, str):
                if domain == entry or domain.endswith("." + entry):
                    return {"domain": entry, "type": "exact_match"}
            elif isinstance(entry, dict):
                # Check if domain matches any key or value in the dict
                for key, value in entry.items():
                    if (
                            isinstance(key, str)
                            and (domain == key or domain.endswith("." + key))
                    ) or (
                            isinstance(value, str)
                            and (domain == value or domain.endswith("." + value))
                    ):
                        return entry
        return None

    def search_discord_servers_by_invite(self, invite_code):
        """Search Discord servers by invite code"""
        matches = []
        if not self.cache["discord_servers"]:
            return matches

        for server_id, server_data in self.cache["discord_servers"].items():
            invite_url = server_data.get("INVITE_URL", "")
            if invite_url:
                server_invite_code = self.extract_invite_code(invite_url)
                if server_invite_code and invite_code.lower() == server_invite_code.lower():
                    matches.append(server_data)

        return matches

    def search_discord_servers_by_id(self, server_id):
        """Search Discord servers by server ID"""
        matches = []
        if not self.cache["discord_servers"]:
            return matches

        for entry_id, server_data in self.cache["discord_servers"].items():
            if server_data.get("SERVER_ID") == server_id:
                matches.append(server_data)

        return matches

    @app_commands.command(
        name="darturl",
        description="Check a URL against DART Project's databases for malicious activity",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="The URL to check against DART Project's databases")
    async def darturl(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        # Refresh cache if empty or stale (older than 1 hour)
        if (
                not self.cache["last_updated"]
                or (datetime.utcnow() - self.cache["last_updated"]).total_seconds() > 3600
        ):
            await self.refresh_cache()

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                await interaction.followup.send("Invalid URL format")
                return
        except:
            await interaction.followup.send("Invalid URL format")
            return

        # Initialize embed - separate title and description to avoid making URL clickable
        embed = discord.Embed(
            title="🔍 URL Security Check",
            description=f"**Checking URL:** `{url}`\n**Powered by:** [DART Project]({self.dart_project_url})",
            color=0x7289DA,
        )

        # Check if cache is loaded
        if not any(self.cache.values()):
            embed.add_field(
                name="⚠️ Database Status",
                value="DART Project databases not loaded. Please try again later.",
                inline=False,
            )
            await interaction.followup.send(embed=embed)
            return

        # Check compromised accounts database
        compromised_matches = []
        if self.cache["compromised_accounts"]:
            for account_id, account_data in self.cache["compromised_accounts"].items():
                if (
                        account_data.get("SURFACE_URL")
                        and url in account_data["SURFACE_URL"]
                ) or (
                        account_data.get("FINAL_URL") and url in account_data["FINAL_URL"]
                ):
                    compromised_matches.append(account_data)

        if compromised_matches:
            embed.add_field(
                name="⚠️ Compromised Account Matches",
                value=f"Found in {len(compromised_matches)} account records",
                inline=False,
            )

            # Add full details of each match
            for i, match in enumerate(
                    compromised_matches[:3], 1
            ):  # Limit to first 3 matches
                embed.add_field(
                    name=f"Match #{i}",
                    value=self.format_embed_field(match),
                    inline=False,
                )

            if len(compromised_matches) > 3:
                embed.add_field(
                    name="Additional Matches",
                    value=f"There are {len(compromised_matches) - 3} more matches not shown",
                    inline=False,
                )

        # Check if it's a Discord URL
        if self.is_discord_url(url):
            # Check for Discord invite matches
            invite_code = self.extract_invite_code(url)
            if invite_code:
                discord_server_matches = self.search_discord_servers_by_invite(invite_code)

                if discord_server_matches:
                    embed.add_field(
                        name="⚠️ Malicious Discord Invite Matches",
                        value=f"Found {len(discord_server_matches)} matches for invite code `{invite_code}`",
                        inline=False,
                    )

                    # Add full details of each match
                    for i, match in enumerate(
                            discord_server_matches[:3], 1
                    ):  # Limit to first 3 matches
                        embed.add_field(
                            name=f"Server Match #{i}",
                            value=self.format_embed_field(match),
                            inline=False,
                        )

                    if len(discord_server_matches) > 3:
                        embed.add_field(
                            name="Additional Server Matches",
                            value=f"There are {len(discord_server_matches) - 3} more matches not shown",
                            inline=False,
                        )
                else:
                    embed.add_field(
                        name="Discord Invite Check",
                        value=f"✅ Invite code `{invite_code}` not found in malicious server database",
                        inline=False,
                    )

            # Also check for exact URL matches in the existing server database
            discord_server_matches = []
            if self.cache["discord_servers"]:
                for server_id, server_data in self.cache["discord_servers"].items():
                    if (
                            server_data.get("INVITE_URL")
                            and url in server_data["INVITE_URL"]
                    ):
                        discord_server_matches.append(server_data)

            if discord_server_matches and not invite_code:  # Only show if not already covered by invite check
                embed.add_field(
                    name="⚠️ Malicious Server URL Matches",
                    value=f"Found in {len(discord_server_matches)} server records",
                    inline=False,
                )
        else:
            # Check global domains database
            domain = self.extract_domain(url)
            domain_match = None

            if self.cache["global_domains"]:
                domain_match = self.check_domain_in_list(
                    domain, self.cache["global_domains"]
                )

            if domain_match:
                embed.add_field(
                    name="⚠️ Global Domains Match",
                    value=f"Domain `{domain}` is flagged in the global domains database",
                    inline=False,
                )
                if isinstance(domain_match, dict) and len(domain_match) > 1:
                    embed.add_field(
                        name="Domain Details",
                        value=self.format_embed_field(domain_match),
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="Global Domains Check",
                    value=f"✅ Domain `{domain}` not found in global domains database",
                    inline=False,
                )

        # Set footer with cache info
        if self.cache["last_updated"]:
            embed.set_footer(
                text=f"DART Project Database • Last updated: {self.cache['last_updated'].strftime('%Y-%m-%d %H:%M UTC')}"
            )
        else:
            embed.set_footer(text="DART Project Database • Cache not loaded")

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="dartinvite",
        description="Check a Discord invite against DART Project's malicious server database",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(invite="Discord invite URL or invite code to check")
    async def dartinvite(self, interaction: discord.Interaction, invite: str):
        await interaction.response.defer()

        # Refresh cache if empty or stale (older than 1 hour)
        if (
                not self.cache["last_updated"]
                or (datetime.utcnow() - self.cache["last_updated"]).total_seconds() > 3600
        ):
            await self.refresh_cache()

        # Extract invite code from URL or use as-is if it's just a code
        invite_code = invite
        if invite.startswith(("http://", "https://")):
            if not self.is_discord_url(invite):
                await interaction.followup.send("Please provide a valid Discord invite URL (discord.com or discord.gg)")
                return

            extracted_code = self.extract_invite_code(invite)
            if not extracted_code:
                await interaction.followup.send("Could not extract invite code from URL")
                return
            invite_code = extracted_code

        # Initialize embed
        embed = discord.Embed(
            title="🔍 Discord Invite Security Check",
            description=f"**Checking Invite Code:** `{invite_code}`\n**Powered by:** [DART Project]({self.dart_project_url})",
            color=0x7289DA,
        )

        # Check if cache is loaded
        if not self.cache["discord_servers"]:
            embed.add_field(
                name="⚠️ Database Status",
                value="DART Project Discord servers database not loaded. Please try again later.",
                inline=False,
            )
            await interaction.followup.send(embed=embed)
            return

        # Search for matches
        matches = self.search_discord_servers_by_invite(invite_code)

        if matches:
            embed.add_field(
                name="⚠️ Malicious Server Matches",
                value=f"Found {len(matches)} matches for invite code `{invite_code}`",
                inline=False,
            )

            # Add full details of each match
            for i, match in enumerate(matches[:3], 1):  # Limit to first 3 matches
                embed.add_field(
                    name=f"Server Match #{i}",
                    value=self.format_embed_field(match),
                    inline=False,
                )

            if len(matches) > 3:
                embed.add_field(
                    name="Additional Matches",
                    value=f"There are {len(matches) - 3} more matches not shown",
                    inline=False,
                )
        else:
            embed.add_field(
                name="✅ No Threats Found",
                value=f"Invite code `{invite_code}` not found in malicious server database",
                inline=False,
            )

        # Set footer with cache info
        if self.cache["last_updated"]:
            embed.set_footer(
                text=f"DART Project Database • Last updated: {self.cache['last_updated'].strftime('%Y-%m-%d %H:%M UTC')}"
            )
        else:
            embed.set_footer(text="DART Project Database • Cache not loaded")

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="dartserver",
        description="Check a Discord server ID against DART Project's malicious server database",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(server_id="Discord server ID to check")
    async def dartserver(self, interaction: discord.Interaction, server_id: str):
        await interaction.response.defer()

        # Validate server ID (should be numeric)
        if not server_id.isdigit():
            await interaction.followup.send("Invalid Discord server ID - must be numeric")
            return

        # Refresh cache if empty or stale (older than 1 hour)
        if (
                not self.cache["last_updated"]
                or (datetime.utcnow() - self.cache["last_updated"]).total_seconds() > 3600
        ):
            await self.refresh_cache()

        # Initialize embed
        embed = discord.Embed(
            title="🔍 Discord Server Security Check",
            description=f"**Checking Server ID:** `{server_id}`\n**Powered by:** [DART Project]({self.dart_project_url})",
            color=0x7289DA,
        )

        # Check if cache is loaded
        if not self.cache["discord_servers"]:
            embed.add_field(
                name="⚠️ Database Status",
                value="DART Project Discord servers database not loaded. Please try again later.",
                inline=False,
            )
            await interaction.followup.send(embed=embed)
            return

        # Search for matches
        matches = self.search_discord_servers_by_id(server_id)

        if matches:
            embed.add_field(
                name="⚠️ Malicious Server Matches",
                value=f"Found {len(matches)} matches for server ID `{server_id}`",
                inline=False,
            )

            # Add full details of each match
            for i, match in enumerate(matches[:3], 1):  # Limit to first 3 matches
                embed.add_field(
                    name=f"Server Match #{i}",
                    value=self.format_embed_field(match),
                    inline=False,
                )

            if len(matches) > 3:
                embed.add_field(
                    name="Additional Matches",
                    value=f"There are {len(matches) - 3} more matches not shown",
                    inline=False,
                )
        else:
            embed.add_field(
                name="✅ No Threats Found",
                value=f"Server ID `{server_id}` not found in malicious server database",
                inline=False,
            )

        # Set footer with cache info
        if self.cache["last_updated"]:
            embed.set_footer(
                text=f"DART Project Database • Last updated: {self.cache['last_updated'].strftime('%Y-%m-%d %H:%M UTC')}"
            )
        else:
            embed.set_footer(text="DART Project Database • Cache not loaded")

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="dartuser",
        description="Check a Discord user ID against DART Project's databases",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user_id="The Discord user ID to check")
    async def dartuser(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer()

        # Validate user ID (should be numeric)
        if not user_id.isdigit():
            await interaction.followup.send("Invalid Discord ID - must be numeric")
            return

        # Refresh cache if empty or stale (older than 1 hour)
        if (
                not self.cache["last_updated"]
                or (datetime.utcnow() - self.cache["last_updated"]).total_seconds() > 3600
        ):
            await self.refresh_cache()

        # Initialize embed - separate title and description to avoid making user ID clickable
        embed = discord.Embed(
            title="🔍 User Security Check",
            description=f"**Checking User ID:** `{user_id}`\n**Powered by:** [DART Project]({self.dart_project_url})",
            color=0x7289DA,
        )

        # Check if cache is loaded
        if not any(self.cache.values()):
            embed.add_field(
                name="⚠️ Database Status",
                value="DART Project databases not loaded. Please try again later.",
                inline=False,
            )
            await interaction.followup.send(embed=embed)
            return

        # Check compromised accounts database
        account_matches = []
        if self.cache["compromised_accounts"]:
            for account_data in self.cache["compromised_accounts"].values():
                if account_data.get("DISCORD_ID") == user_id:
                    account_matches.append(account_data)

        if account_matches:
            embed.add_field(
                name="⚠️ Compromised Account Matches",
                value=f"Found in {len(account_matches)} account records",
                inline=False,
            )

            # Add full details of each match
            for i, match in enumerate(
                    account_matches[:3], 1
            ):  # Limit to first 3 matches
                embed.add_field(
                    name=f"Account Match #{i}",
                    value=self.format_embed_field(match),
                    inline=False,
                )

            if len(account_matches) > 3:
                embed.add_field(
                    name="Additional Account Matches",
                    value=f"There are {len(account_matches) - 3} more matches not shown",
                    inline=False,
                )
        else:
            embed.add_field(
                name="Compromised Accounts Check",
                value="✅ Not found in compromised accounts database",
                inline=False,
            )

        # Check Discord IDs database
        if self.cache["discord_ids"] and user_id in self.cache["discord_ids"]:
            id_data = self.cache["discord_ids"][user_id]
            embed.add_field(
                name="⚠️ Threat ID Match",
                value=self.format_embed_field(id_data),
                inline=False,
            )
        else:
            embed.add_field(
                name="Threat IDs Check",
                value="✅ Not found in threat IDs database",
                inline=False,
            )

        # Set footer with cache info
        if self.cache["last_updated"]:
            embed.set_footer(
                text=f"DART Project Database • Last updated: {self.cache['last_updated'].strftime('%Y-%m-%d %H:%M UTC')}"
            )
        else:
            embed.set_footer(text="DART Project Database • Cache not loaded")

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="dartstats",
        description="Get statistics about the DART Project databases",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def dartstats(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Refresh cache if empty or stale (older than 1 hour)
        if (
                not self.cache["last_updated"]
                or (datetime.utcnow() - self.cache["last_updated"]).total_seconds() > 3600
        ):
            await self.refresh_cache()

        # Initialize embed with clickable title to DART Project
        embed = discord.Embed(
            title="📊 DART Project Statistics", color=0x7289DA, url=self.dart_project_url
        )

        # Check if cache is loaded
        if not self.cache["stats"]:
            embed.description = (
                "⚠️ DART Project statistics not loaded. Please try again later."
            )
            await interaction.followup.send(embed=embed)
            return

        try:
            stats = self.parse_stats(self.cache["stats"])

            # Add main statistics
            embed.add_field(
                name="📈 Database Statistics",
                value=f"**Total Cases:** {stats.get('Total Cases', 'N/A')}\n"
                      f"**Protected Members:** {stats.get('Protected Members', 'N/A')}",
                inline=False,
            )

            # Add database entries
            embed.add_field(
                name="🗄️ Database Entries",
                value=f"**Discord IDs:** {stats.get('Discord IDs', 'N/A')}\n"
                      f"**Discord Servers:** {stats.get('Discord Servers', 'N/A')}\n"
                      f"**Global Domains:** {stats.get('Global Domains', 'N/A')}",
                inline=False,
            )

            # Add categorized counts
            embed.add_field(
                name="📋 Categories",
                value=f"**Account Types:** {stats.get('Account Types', 'N/A')}\n"
                      f"**Behaviors:** {stats.get('Behaviors', 'N/A')}\n"
                      f"**Attack Methods:** {stats.get('Attack Methods', 'N/A')}\n"
                      f"**Countries:** {stats.get('Countries', 'N/A')}",
                inline=False,
            )

            # Set footer with cache info
            if self.cache["last_updated"]:
                embed.set_footer(
                    text=f"DART Project Database • Last updated: {self.cache['last_updated'].strftime('%Y-%m-%d %H:%M UTC')}"
                )
            else:
                embed.set_footer(text="DART Project Database • Cache not loaded")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error(f"Error parsing stats: {e}")
            embed.description = "⚠️ Error parsing DART Project statistics."
            await interaction.followup.send(embed=embed)

    def cog_unload(self):
        asyncio.create_task(self.session.close())


async def setup(bot):
    await bot.add_cog(DARTCommands(bot))