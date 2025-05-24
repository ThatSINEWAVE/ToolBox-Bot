import aiohttp
import asyncio
import os
import json
from datetime import datetime
import logging
from urllib.parse import urlparse
import time


class URLChecker:
    def __init__(self):
        self.virustotal_token = os.getenv("VIRUSTOTAL_API_TOKEN")
        self.urlscan_token = os.getenv("URLSCAN_API_TOKEN")
        self.ipinfo_token = os.getenv("IPINFO_API_TOKEN")
        self.urlvoid_token = None  # URLVoid doesn't require API key for basic checks

    async def check_virustotal(self, url):
        """Check URL with VirusTotal API"""
        if not self.virustotal_token:
            return {"error": "VirusTotal API token not configured"}

        headers = {"x-apikey": self.virustotal_token}

        try:
            async with aiohttp.ClientSession() as session:
                # Submit URL for analysis
                data = {"url": url}
                async with session.post(
                    "https://www.virustotal.com/api/v3/urls", headers=headers, data=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        url_id = result.get("data", {}).get("id", "")

                        # Get analysis results
                        await asyncio.sleep(2)  # Wait for analysis
                        async with session.get(
                            f"https://www.virustotal.com/api/v3/analyses/{url_id}",
                            headers=headers,
                        ) as analysis_response:
                            if analysis_response.status == 200:
                                analysis = await analysis_response.json()
                                stats = (
                                    analysis.get("data", {})
                                    .get("attributes", {})
                                    .get("stats", {})
                                )
                                return {
                                    "malicious": stats.get("malicious", 0),
                                    "suspicious": stats.get("suspicious", 0),
                                    "clean": stats.get("harmless", 0),
                                    "unrated": stats.get("undetected", 0),
                                    "total": sum(stats.values()) if stats else 0,
                                }
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            logging.error(f"VirusTotal check error: {e}")
            return {"error": str(e)}

    async def check_urlscan(self, url):
        """Check URL with URLScan.io API"""
        if not self.urlscan_token:
            return {"error": "URLScan API token not configured"}

        headers = {"API-Key": self.urlscan_token}

        try:
            async with aiohttp.ClientSession() as session:
                # Submit URL for scanning
                data = {"url": url, "visibility": "unlisted"}
                async with session.post(
                    "https://urlscan.io/api/v1/scan/", headers=headers, json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        scan_id = result.get("uuid")

                        # Wait for scan to complete
                        await asyncio.sleep(10)

                        # Get results
                        async with session.get(
                            f"https://urlscan.io/api/v1/result/{scan_id}/"
                        ) as result_response:
                            if result_response.status == 200:
                                scan_result = await result_response.json()
                                verdicts = scan_result.get("verdicts", {})
                                return {
                                    "overall_verdict": verdicts.get("overall", {}).get(
                                        "score", 0
                                    ),
                                    "malicious": verdicts.get("overall", {}).get(
                                        "malicious", False
                                    ),
                                    "categories": verdicts.get("overall", {}).get(
                                        "categories", []
                                    ),
                                    "screenshot": scan_result.get("task", {}).get(
                                        "screenshotURL", ""
                                    ),
                                    "scan_url": f"https://urlscan.io/result/{scan_id}/",
                                }
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            logging.error(f"URLScan check error: {e}")
            return {"error": str(e)}

    async def check_urlvoid(self, url):
        """Check URL with URLVoid (basic check without API key)"""
        try:
            # Extract domain from URL
            domain = urlparse(url).netloc
            if not domain:
                return {"error": "Invalid URL format"}

            async with aiohttp.ClientSession() as session:
                # URLVoid requires domain, not full URL
                check_url = f"http://www.urlvoid.com/scan/{domain}/"
                async with session.get(check_url) as response:
                    if response.status == 200:
                        # This is a simplified check - in reality, you'd parse the HTML
                        # or use their API if you have a key
                        return {
                            "domain": domain,
                            "status": "checked",
                            "note": "Manual verification recommended",
                        }
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            logging.error(f"URLVoid check error: {e}")
            return {"error": str(e)}

    async def check_ipinfo(self, url):
        """Get IP and geolocation info for the URL"""
        if not self.ipinfo_token:
            return {"error": "IPInfo API token not configured"}

        try:
            # Extract domain from URL
            domain = urlparse(url).netloc
            if not domain:
                return {"error": "Invalid URL format"}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://ipinfo.io/{domain}?token={self.ipinfo_token}"
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "ip": result.get("ip", "Unknown"),
                            "country": result.get("country", "Unknown"),
                            "region": result.get("region", "Unknown"),
                            "city": result.get("city", "Unknown"),
                            "org": result.get("org", "Unknown"),
                            "timezone": result.get("timezone", "Unknown"),
                        }
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            logging.error(f"IPInfo check error: {e}")
            return {"error": str(e)}

    async def check_all(self, url):
        """Run all checks concurrently"""
        tasks = [
            self.check_virustotal(url),
            self.check_urlscan(url),
            self.check_urlvoid(url),
            self.check_ipinfo(url),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "virustotal": results[0]
            if not isinstance(results[0], Exception)
            else {"error": str(results[0])},
            "urlscan": results[1]
            if not isinstance(results[1], Exception)
            else {"error": str(results[1])},
            "urlvoid": results[2]
            if not isinstance(results[2], Exception)
            else {"error": str(results[2])},
            "ipinfo": results[3]
            if not isinstance(results[3], Exception)
            else {"error": str(results[3])},
        }

    def save_to_history(self, url, results):
        """Save scan results to history file"""
        try:
            # Ensure history directory exists
            os.makedirs("history", exist_ok=True)

            history_file = "history/Checked-URLs.json"

            # Load existing history
            history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r") as f:
                        history = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    history = []

            # Add new entry
            entry = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "results": results,
            }

            history.append(entry)

            # Save updated history
            with open(history_file, "w") as f:
                json.dump(history, f, indent=2)

            logging.info(f"Saved scan results for {url} to history")

        except Exception as e:
            logging.error(f"Error saving to history: {e}")
