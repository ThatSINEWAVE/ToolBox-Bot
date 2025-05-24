import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.url_checker import URLChecker
import asyncio


class CheckURLCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url_checker = URLChecker()

    # Create the initial progress embed
    def create_progress_embed(self, url):
        embed = discord.Embed(
            title="🔍 URL Security Check",
            description=f"Checking URL: `{url}`",
            color=0xFFA500,  # Orange color for progress
        )

        embed.add_field(name="Status", value="🔄 Scanning in progress...", inline=False)

        embed.add_field(
            name="Services",
            value="• VirusTotal: ⏳ Pending\n• URLScan.io: ⏳ Pending\n• URLVoid: ⏳ Pending\n• IPInfo: ⏳ Pending",
            inline=False,
        )

        embed.set_footer(text="This may take up to 30 seconds...")
        return embed

    # Create the final results embed
    def create_results_embed(self, url, results):
        # Determine overall safety based on results
        is_safe = True
        risk_level = "🟢 Low Risk"

        # Check VirusTotal results
        vt_result = results.get("virustotal", {})
        if not vt_result.get("error"):
            malicious = vt_result.get("malicious", 0)
            suspicious = vt_result.get("suspicious", 0)
            if malicious > 0:
                is_safe = False
                risk_level = "🔴 High Risk"
            elif suspicious > 2:
                risk_level = "🟡 Medium Risk"

        # Check URLScan results
        urlscan_result = results.get("urlscan", {})
        if not urlscan_result.get("error") and urlscan_result.get("malicious"):
            is_safe = False
            risk_level = "🔴 High Risk"

        # Set embed color based on risk
        color = (
            0x00FF00
            if is_safe and risk_level == "🟢 Low Risk"
            else (0xFFFF00 if "Medium" in risk_level else 0xFF0000)
        )

        embed = discord.Embed(
            title="🔍 URL Security Check - Complete",
            description=f"Results for: `{url}`",
            color=color,
        )

        embed.add_field(name="Overall Assessment", value=risk_level, inline=False)

        # VirusTotal Results
        vt_text = "❌ Error occurred"
        if not vt_result.get("error"):
            malicious = vt_result.get("malicious", 0)
            suspicious = vt_result.get("suspicious", 0)
            clean = vt_result.get("clean", 0)
            total = vt_result.get("total", 0)
            vt_text = f"🛡️ {malicious} malicious, {suspicious} suspicious\n📊 {clean} clean out of {total} engines"
        else:
            vt_text = f"❌ {vt_result['error']}"

        embed.add_field(name="🦠 VirusTotal", value=vt_text, inline=True)

        # URLScan Results
        urlscan_text = "❌ Error occurred"
        if not urlscan_result.get("error"):
            malicious = "Yes" if urlscan_result.get("malicious") else "No"
            score = urlscan_result.get("overall_verdict", 0)
            categories = urlscan_result.get("categories", [])
            cat_text = ", ".join(categories) if categories else "None"
            urlscan_text = (
                f"🚨 Malicious: {malicious}\n📈 Score: {score}\n🏷️ Categories: {cat_text}"
            )

            scan_url = urlscan_result.get("scan_url")
            if scan_url:
                urlscan_text += f"\n🔗 [View Report]({scan_url})"
        else:
            urlscan_text = f"❌ {urlscan_result['error']}"

        embed.add_field(name="🌐 URLScan.io", value=urlscan_text, inline=True)

        # URLVoid Results
        urlvoid_result = results.get("urlvoid", {})
        urlvoid_text = "❌ Error occurred"
        if not urlvoid_result.get("error"):
            domain = urlvoid_result.get("domain", "Unknown")
            urlvoid_text = f"🌐 Domain: {domain}\n✅ Basic check completed"
        else:
            urlvoid_text = f"❌ {urlvoid_result['error']}"

        embed.add_field(name="🔍 URLVoid", value=urlvoid_text, inline=True)

        # IPInfo Results
        ipinfo_result = results.get("ipinfo", {})
        ipinfo_text = "❌ Error occurred"
        if not ipinfo_result.get("error"):
            ip = ipinfo_result.get("ip", "Unknown")
            country = ipinfo_result.get("country", "Unknown")
            city = ipinfo_result.get("city", "Unknown")
            org = ipinfo_result.get("org", "Unknown")
            ipinfo_text = f"🌍 IP: {ip}\n📍 Location: {city}, {country}\n🏢 Org: {org}"
        else:
            ipinfo_text = f"❌ {ipinfo_result['error']}"

        embed.add_field(name="📍 IPInfo", value=ipinfo_text, inline=True)

        embed.set_footer(
            text="⚠️ Always exercise caution when visiting unfamiliar URLs"
        )
        return embed

    # Check a URL against multiple security services
    @app_commands.command(
        name="checkurl",
        description="Check a URL for security threats using multiple services",
    )
    @app_commands.describe(url="The URL to check for security threats")
    async def checkurl(self, interaction: discord.Interaction, url: str):
        try:
            # Validate URL format
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            # Send initial progress embed
            progress_embed = self.create_progress_embed(url)
            await interaction.response.send_message(embed=progress_embed)

            # Perform the checks
            results = await self.url_checker.check_all(url)

            # Save to history
            self.url_checker.save_to_history(url, results)

            # Create and send final results embed
            results_embed = self.create_results_embed(url, results)
            await interaction.edit_original_response(embed=results_embed)

            logging.info(f"URL check completed for {url} by {interaction.user}")

        except Exception as e:
            logging.error(f"Error in checkurl command: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while checking the URL: {str(e)}",
                color=0xFF0000,
            )

            try:
                await interaction.edit_original_response(embed=error_embed)
            except:
                await interaction.followup.send(embed=error_embed)


async def setup(bot):
    await bot.add_cog(CheckURLCommand(bot))
