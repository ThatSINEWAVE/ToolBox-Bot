import aiohttp
import asyncio
import os
import json
import base64
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

    # Check URL with VirusTotal API
    async def check_virustotal(self, url):
        if not self.virustotal_token:
            return {"error": "VirusTotal API token not configured"}

        headers = {"x-apikey": self.virustotal_token}

        try:
            async with aiohttp.ClientSession() as session:
                # First, try to get existing analysis using URL ID
                url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")

                # Check if URL was already analyzed
                async with session.get(
                    f"https://www.virustotal.com/api/v3/urls/{url_id}",
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        stats = (
                            result.get("data", {})
                            .get("attributes", {})
                            .get("last_analysis_stats", {})
                        )
                        if stats:  # If we have existing analysis
                            return {
                                "malicious": stats.get("malicious", 0),
                                "suspicious": stats.get("suspicious", 0),
                                "clean": stats.get("harmless", 0),
                                "unrated": stats.get("undetected", 0),
                                "total": sum(stats.values()) if stats else 0,
                                "scan_date": result.get("data", {})
                                .get("attributes", {})
                                .get("last_analysis_date", ""),
                            }

                # If no existing analysis, submit URL for new analysis
                data = {"url": url}
                async with session.post(
                    "https://www.virustotal.com/api/v3/urls", headers=headers, data=data
                ) as submit_response:
                    if submit_response.status == 200:
                        submit_result = await submit_response.json()
                        analysis_id = submit_result.get("data", {}).get("id", "")

                        if not analysis_id:
                            return {"error": "Failed to get analysis ID"}

                        # Wait for analysis to complete (with retries)
                        max_retries = 6
                        for attempt in range(max_retries):
                            await asyncio.sleep(10)  # Wait between checks

                            async with session.get(
                                f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                                headers=headers,
                            ) as analysis_response:
                                if analysis_response.status == 200:
                                    analysis = await analysis_response.json()
                                    attributes = analysis.get("data", {}).get(
                                        "attributes", {}
                                    )

                                    # Check if analysis is complete
                                    if attributes.get("status") == "completed":
                                        stats = attributes.get("stats", {})
                                        return {
                                            "malicious": stats.get("malicious", 0),
                                            "suspicious": stats.get("suspicious", 0),
                                            "clean": stats.get("harmless", 0),
                                            "unrated": stats.get("undetected", 0),
                                            "total": sum(stats.values())
                                            if stats
                                            else 0,
                                            "scan_date": attributes.get("date", ""),
                                        }
                                    elif attributes.get("status") == "queued":
                                        continue  # Keep waiting
                                    else:
                                        return {
                                            "error": f"Analysis failed with status: {attributes.get('status')}"
                                        }

                        return {"error": "Analysis timeout - please try again later"}
                    else:
                        return {
                            "error": f"Failed to submit URL: HTTP {submit_response.status}"
                        }

        except Exception as e:
            logging.error(f"VirusTotal check error: {e}")
            return {"error": str(e)}

    # Check URL with URLScan.io API
    async def check_urlscan(self, url):
        if not self.urlscan_token:
            return {"error": "URLScan API token not configured"}

        headers = {"API-Key": self.urlscan_token, "Content-Type": "application/json"}

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

                        if not scan_id:
                            return {"error": "Failed to get scan ID"}

                        # Wait for scan to complete with retries
                        max_retries = 12  # Up to 2 minutes
                        for attempt in range(max_retries):
                            await asyncio.sleep(10)

                            try:
                                async with session.get(
                                    f"https://urlscan.io/api/v1/result/{scan_id}/"
                                ) as result_response:
                                    if result_response.status == 200:
                                        scan_result = await result_response.json()

                                        # Extract verdicts safely
                                        verdicts = scan_result.get("verdicts", {})
                                        overall = verdicts.get("overall", {})

                                        return {
                                            "overall_verdict": overall.get("score", 0),
                                            "malicious": overall.get(
                                                "malicious", False
                                            ),
                                            "categories": overall.get("categories", []),
                                            "screenshot": scan_result.get(
                                                "task", {}
                                            ).get("screenshotURL", ""),
                                            "scan_url": f"https://urlscan.io/result/{scan_id}/",
                                            "brands": scan_result.get("brands", []),
                                        }
                                    elif result_response.status == 404:
                                        # Scan still in progress
                                        continue
                                    else:
                                        return {
                                            "error": f"Result fetch failed: HTTP {result_response.status}"
                                        }
                            except Exception as retry_error:
                                logging.warning(
                                    f"URLScan retry {attempt + 1} failed: {retry_error}"
                                )
                                if attempt == max_retries - 1:
                                    return {
                                        "error": f"Scan timeout after retries: {str(retry_error)}"
                                    }
                                continue

                        return {"error": "Scan timeout - results not ready"}

                    elif response.status == 400:
                        error_text = await response.text()
                        return {"error": f"Bad request: {error_text}"}
                    elif response.status == 429:
                        return {"error": "Rate limit exceeded - please try again later"}
                    else:
                        return {
                            "error": f"Scan submission failed: HTTP {response.status}"
                        }

        except Exception as e:
            logging.error(f"URLScan check error: {e}")
            return {"error": str(e)}

    # Check URL with URLVoid API
    async def check_urlvoid(self, url):
        try:
            # Extract domain from URL
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            if not domain:
                return {"error": "Invalid URL format"}

            # Remove 'www.' prefix if present
            if domain.startswith("www."):
                domain = domain[4:]

            async with aiohttp.ClientSession() as session:
                # Use URLVoid's basic API endpoint
                check_url = f"https://www.urlvoid.com/api1000/{domain}/"

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }

                async with session.get(check_url, headers=headers) as response:
                    if response.status == 200:
                        response_text = await response.text()

                        # Basic analysis of response
                        detections = 0
                        if "ALERT" in response_text.upper():
                            detections += 1
                        if "MALWARE" in response_text.upper():
                            detections += 2
                        if "PHISHING" in response_text.upper():
                            detections += 2

                        return {
                            "domain": domain,
                            "status": "checked",
                            "detections": detections,
                            "risk_level": "high"
                            if detections >= 2
                            else "medium"
                            if detections == 1
                            else "low",
                            "note": "Basic check completed",
                        }
                    else:
                        return {"error": f"HTTP {response.status}"}

        except Exception as e:
            logging.error(f"URLVoid check error: {e}")
            return {"error": str(e)}

    # Get IP and geolocation info for the URL
    async def check_ipinfo(self, url):
        if not self.ipinfo_token:
            return {"error": "IPInfo API token not configured"}

        try:
            # Extract domain from URL
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            if not domain:
                return {"error": "Invalid URL format"}

            # Remove 'www.' prefix if present
            if domain.startswith("www."):
                domain = domain[4:]

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://ipinfo.io/{domain}?token={self.ipinfo_token}"
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        # Check if we got an IP address back
                        if "ip" not in result:
                            return {"error": "Domain not found or invalid"}

                        return {
                            "ip": result.get("ip", "Unknown"),
                            "country": result.get("country", "Unknown"),
                            "region": result.get("region", "Unknown"),
                            "city": result.get("city", "Unknown"),
                            "org": result.get("org", "Unknown"),
                            "timezone": result.get("timezone", "Unknown"),
                            "loc": result.get("loc", "Unknown"),
                            "postal": result.get("postal", "Unknown"),
                        }
                    elif response.status == 404:
                        return {"error": "Domain not found"}
                    elif response.status == 429:
                        return {"error": "Rate limit exceeded"}
                    else:
                        return {"error": f"HTTP {response.status}"}
        except Exception as e:
            logging.error(f"IPInfo check error: {e}")
            return {"error": str(e)}

    # Run all checks concurrently with better error handling
    async def check_all(self, url):
        # Create tasks for concurrent execution
        tasks = []

        # Add VirusTotal check
        tasks.append(("virustotal", self.check_virustotal(url)))

        # Add URLScan check
        tasks.append(("urlscan", self.check_urlscan(url)))

        # Add URLVoid check
        tasks.append(("urlvoid", self.check_urlvoid(url)))

        # Add IPInfo check
        tasks.append(("ipinfo", self.check_ipinfo(url)))

        # Run all tasks concurrently with timeout
        results = {}

        for service_name, task in tasks:
            try:
                # Set timeout for each service
                result = await asyncio.wait_for(task, timeout=60.0)
                results[service_name] = result
            except asyncio.TimeoutError:
                results[service_name] = {"error": "Request timeout"}
            except Exception as e:
                results[service_name] = {"error": str(e)}

        return results

    # Save scan results to history file with better error handling
    def save_to_history(self, url, results):
        try:
            # Ensure history directory exists
            os.makedirs("history", exist_ok=True)

            history_file = "history/Checked-URLs.json"

            # Load existing history
            history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r", encoding="utf-8") as f:
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

            # Keep only last 1000 entries to prevent file from growing too large
            if len(history) > 1000:
                history = history[-1000:]

            # Save updated history
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            logging.info(f"Saved scan results for {url} to history")

        except Exception as e:
            logging.error(f"Error saving to history: {e}")
