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

        embed.set_footer(text="This may take up to 2 minutes for complete analysis...")
        return embed

    # Create the final results embed with improved analysis
    def create_results_embed(self, url, results):
        # Determine overall safety based on results
        is_safe = True
        risk_level = "🟢 Low Risk"
        risk_factors = []

        # Safely check VirusTotal results
        vt_result = results.get("virustotal", {})
        if isinstance(vt_result, dict) and not vt_result.get("error"):
            malicious = (
                vt_result.get("malicious", 0)
                if isinstance(vt_result.get("malicious"), int)
                else 0
            )
            suspicious = (
                vt_result.get("suspicious", 0)
                if isinstance(vt_result.get("suspicious"), int)
                else 0
            )
            total = (
                vt_result.get("total", 0)
                if isinstance(vt_result.get("total"), int)
                else 0
            )

            if malicious > 0:
                is_safe = False
                risk_level = "🔴 High Risk"
                risk_factors.append(
                    f"VirusTotal: {malicious}/{total} engines detected malware"
                )
            elif suspicious > 3:
                if risk_level == "🟢 Low Risk":
                    risk_level = "🟡 Medium Risk"
                risk_factors.append(
                    f"VirusTotal: {suspicious} engines flagged as suspicious"
                )

        # Safely check URLScan results
        urlscan_result = results.get("urlscan", {})
        if isinstance(urlscan_result, dict) and not urlscan_result.get("error"):
            if urlscan_result.get("malicious"):
                is_safe = False
                risk_level = "🔴 High Risk"
                risk_factors.append("URLScan.io detected malicious content")

            score = urlscan_result.get("overall_verdict", 0)
            if isinstance(score, (int, float)) and score > 50:
                if risk_level == "🟢 Low Risk":
                    risk_level = "🟡 Medium Risk"
                risk_factors.append(f"URLScan.io suspicion score: {score}/100")

        # Safely check URLVoid results
        urlvoid_result = results.get("urlvoid", {})
        if isinstance(urlvoid_result, dict) and not urlvoid_result.get("error"):
            risk = urlvoid_result.get("risk_level", "low")
            if isinstance(risk, str):
                if risk == "high":
                    is_safe = False
                    risk_level = "🔴 High Risk"
                    risk_factors.append("URLVoid detected high risk indicators")
                elif risk == "medium" and risk_level == "🟢 Low Risk":
                    risk_level = "🟡 Medium Risk"
                    risk_factors.append("URLVoid detected medium risk indicators")

        # Set embed color based on risk
        color = (
            0x00FF00
            if risk_level == "🟢 Low Risk"
            else (0xFFFF00 if "Medium" in risk_level else 0xFF0000)
        )

        embed = discord.Embed(
            title="🔍 URL Security Check - Complete",
            description=f"Results for: `{url}`",
            color=color,
        )

        embed.add_field(name="Overall Assessment", value=risk_level, inline=False)

        if risk_factors:
            embed.add_field(
                name="⚠️ Risk Factors",
                value="\n".join(f"• {factor}" for factor in risk_factors[:5]),
                inline=False,
            )

        # VirusTotal Results - with safe type checking
        vt_result = results.get("virustotal", {})
        if isinstance(vt_result, dict) and not vt_result.get("error"):
            malicious = (
                vt_result.get("malicious", 0)
                if isinstance(vt_result.get("malicious"), int)
                else 0
            )
            suspicious = (
                vt_result.get("suspicious", 0)
                if isinstance(vt_result.get("suspicious"), int)
                else 0
            )
            clean = (
                vt_result.get("clean", 0)
                if isinstance(vt_result.get("clean"), int)
                else 0
            )
            total = (
                vt_result.get("total", 0)
                if isinstance(vt_result.get("total"), int)
                else 0
            )
            scan_date = vt_result.get("scan_date", "Unknown")

            vt_text = f"🛡️ **Malicious:** {malicious}/{total}\n"
            vt_text += f"⚠️ **Suspicious:** {suspicious}/{total}\n"
            vt_text += f"✅ **Clean:** {clean}/{total}"

            if isinstance(scan_date, str) and scan_date and scan_date != "Unknown":
                vt_text += f"\n📅 Last scan: {scan_date[:10]}"
        else:
            error_msg = (
                vt_result.get("error", "Unknown error")
                if isinstance(vt_result, dict)
                else "Invalid response format"
            )
            vt_text = f"❌ {error_msg}"

        embed.add_field(name="🦠 VirusTotal", value=vt_text, inline=True)

        # URLScan Results - with safe type checking
        urlscan_result = results.get("urlscan", {})
        if isinstance(urlscan_result, dict) and not urlscan_result.get("error"):
            malicious = urlscan_result.get("malicious", False)
            malicious_status = "✅ Clean" if not malicious else "🚨 **MALICIOUS**"
            score = urlscan_result.get("overall_verdict", 0)
            categories = urlscan_result.get("categories", [])
            brands = urlscan_result.get("brands", [])

            urlscan_text = f"🚨 Status: {malicious_status}\n📈 Score: {score}/100"

            if isinstance(categories, list) and categories:
                cat_text = ", ".join(str(cat) for cat in categories[:3])
                urlscan_text += f"\n🏷️ Categories: {cat_text}"

            if isinstance(brands, list) and brands:
                brand_text = ", ".join(str(brand) for brand in brands[:2])
                urlscan_text += f"\n🏢 Brands: {brand_text}"

            scan_url = urlscan_result.get("scan_url")
            if isinstance(scan_url, str) and scan_url:
                urlscan_text += f"\n🔗 [View Report]({scan_url})"
        else:
            error_msg = (
                urlscan_result.get("error", "Unknown error")
                if isinstance(urlscan_result, dict)
                else "Invalid response format"
            )
            urlscan_text = f"❌ {error_msg}"

        embed.add_field(name="🌐 URLScan.io", value=urlscan_text, inline=True)

        # URLVoid Results - with safe type checking
        urlvoid_result = results.get("urlvoid", {})
        if isinstance(urlvoid_result, dict) and not urlvoid_result.get("error"):
            domain = urlvoid_result.get("domain", "Unknown")
            risk = urlvoid_result.get("risk_level", "low")
            detections = urlvoid_result.get("detections", 0)

            risk_emoji = "🟢" if risk == "low" else ("🟡" if risk == "medium" else "🔴")
            urlvoid_text = f"🌐 Domain: {domain}\n{risk_emoji} Risk: {str(risk).title()}"

            if isinstance(detections, int) and detections > 0:
                urlvoid_text += f"\n⚠️ Detections: {detections}"
        else:
            error_msg = (
                urlvoid_result.get("error", "Unknown error")
                if isinstance(urlvoid_result, dict)
                else "Invalid response format"
            )
            urlvoid_text = f"❌ {error_msg}"

        embed.add_field(name="🔍 URLVoid", value=urlvoid_text, inline=True)

        # IPInfo Results - with safe type checking
        ipinfo_result = results.get("ipinfo", {})
        if isinstance(ipinfo_result, dict) and not ipinfo_result.get("error"):
            ip = ipinfo_result.get("ip", "Unknown")
            country = ipinfo_result.get("country", "Unknown")
            city = ipinfo_result.get("city", "Unknown")
            org = ipinfo_result.get("org", "Unknown")

            ipinfo_text = f"🌍 IP: `{ip}`\n📍 Location: {city}, {country}"
            if isinstance(org, str) and org and org != "Unknown":
                # Truncate long org names
                org_display = org[:30] + "..." if len(org) > 30 else org
                ipinfo_text += f"\n🏢 Org: {org_display}"
        else:
            error_msg = (
                ipinfo_result.get("error", "Unknown error")
                if isinstance(ipinfo_result, dict)
                else "Invalid response format"
            )
            ipinfo_text = f"❌ {error_msg}"

        embed.add_field(name="📍 IPInfo", value=ipinfo_text, inline=True)

        # Add warning footer based on risk level
        if risk_level == "🔴 High Risk":
            footer_text = "⚠️ HIGH RISK: Avoid visiting this URL!"
        elif risk_level == "🟡 Medium Risk":
            footer_text = "⚠️ MEDIUM RISK: Exercise extreme caution!"
        else:
            footer_text = (
                "ℹ️ Always verify URLs before clicking, even if they appear safe."
            )

        embed.set_footer(text=footer_text)
        return embed

    # Check a URL against multiple security services
    @app_commands.command(
        name="checkurl",
        description="Check a URL for security threats using multiple services",
    )
    @app_commands.describe(url="The URL to check for security threats")
    async def checkurl(self, interaction: discord.Interaction, url: str):
        try:
            # Validate and normalize URL format
            original_url = url

            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            # Basic URL validation
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if not parsed.netloc:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Invalid URL",
                        description="Please provide a valid URL format.",
                        color=0xFF0000,
                    ),
                    ephemeral=True,
                )
                return

            # Send initial progress embed
            progress_embed = self.create_progress_embed(url)
            await interaction.response.send_message(
                embed=progress_embed, ephemeral=False
            )

            try:
                # Perform the checks with timeout
                results = await asyncio.wait_for(
                    self.url_checker.check_all(url), timeout=120.0  # 2 minute timeout
                )

                # Debug logging
                logging.info(f"Raw results for {url}: {results}")

                # Validate results structure
                if not isinstance(results, dict):
                    raise ValueError("Invalid results format returned from URL checker")

                # Ensure all expected keys exist and are proper types
                expected_services = ["virustotal", "urlscan", "urlvoid", "ipinfo"]
                for service in expected_services:
                    if service not in results:
                        results[service] = {"error": "Service check failed"}
                    elif not isinstance(results[service], dict):
                        logging.warning(
                            f"Invalid result type for {service}: {type(results[service])}"
                        )
                        results[service] = {
                            "error": f"Invalid response format: {type(results[service])}"
                        }

                # Save to history
                try:
                    self.url_checker.save_to_history(url, results)
                except Exception as history_error:
                    logging.error(f"Failed to save to history: {history_error}")

                # Create and send final results embed
                results_embed = self.create_results_embed(url, results)
                await interaction.edit_original_response(embed=results_embed)

                logging.info(f"URL check completed for {url} by {interaction.user}")

            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ Timeout",
                    description="The URL check took too long to complete. This might indicate network issues or the URL is unresponsive.",
                    color=0xFF9900,
                )
                timeout_embed.add_field(
                    name="Recommendation",
                    value="This timeout could be a red flag. Exercise extreme caution with this URL.",
                    inline=False,
                )
                await interaction.edit_original_response(embed=timeout_embed)

        except Exception as e:
            logging.error(f"Error in checkurl command: {e}")
            logging.error(f"Error type: {type(e)}")
            import traceback

            logging.error(f"Traceback: {traceback.format_exc()}")

            error_embed = discord.Embed(
                title="❌ Error",
                description=f"An unexpected error occurred while checking the URL.",
                color=0xFF0000,
            )
            error_embed.add_field(
                name="Error Details", value=f"```{str(e)[:1000]}```", inline=False
            )

            try:
                await interaction.edit_original_response(embed=error_embed)
            except:
                try:
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                except:
                    # Last resort - send a simple message
                    logging.error("Failed to send error embed, sending simple message")
                    await interaction.followup.send(
                        "An error occurred during URL checking.", ephemeral=True
                    )


async def setup(bot):
    await bot.add_cog(CheckURLCommand(bot))
