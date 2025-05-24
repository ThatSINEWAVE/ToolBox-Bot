<div align="center">

# ToolBox Bot

ToolBox is a feature-rich Discord bot designed to provide security analysis tools, URL checking, metadata extraction, and various cybersecurity utilities. The bot integrates with multiple security APIs and services to help users analyze potential threats and gather information about domains, IPs, files, and more.

</div>

## Features

### Security Analysis
- **URL Scanning**: Check URLs against multiple security services (VirusTotal, URLScan.io, URLVoid)
- **IP Analysis**: Get geolocation and network information for IP addresses
- **Domain Reconnaissance**: Perform WHOIS lookups, DNS enumeration, and subdomain discovery
- **DART Project Integration**: Check URLs and user IDs against the DART Project threat database
- **CVE Lookup**: Get details about Common Vulnerabilities and Exposures

<div align="center">

## ☕ [Support my work on Ko-Fi](https://ko-fi.com/thatsinewave)

</div>

### Network Utilities
- **DNS Lookup**: Enumerate DNS records for domains
- **SSL/TLS Check**: Analyze SSL certificates for domains
- **Headers Analysis**: Check HTTP security headers of websites
- **Port Scanning**: Perform quick port scans on IP addresses (via Shodan)

### File Analysis
- **Metadata Extraction**: Extract metadata from images, PDFs, and Office documents
- **File Type Detection**: Identify file types and analyze their contents

### URL Utilities
- **URL Unshortening**: Reveal the final destination of shortened URLs
- **Redirect Following**: Track URL redirect chains

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- Discord bot token
- API keys for various services (see below)
- Required Python packages (install via `pip install -r requirements.txt`)

### Configuration
1. Create a `.env` file in the project root with the following variables:
```
# URLSCAN.IO API TOKEN
URLSCAN_API_TOKEN=TOKEN

# IPINFO.IO API TOKEN
IPINFO_API_TOKEN=TOKEN

# VIRUSTOTAL API TOKEN
VIRUSTOTAL_API_TOKEN=TOKEN

# SHODAN API TOKEN
SHODAN_API_TOKEN=TOKEN

# CVE SEARCH TOKEN
CVE_SEARCH_API=TOKEN

# DISCORD BOT TOKEN
DISCORD_TOKEN=TOKEN

# DISCORD BOT ID
CLIENT_ID=ID
```

2. Install required dependencies:
```bash
pip install discord.py python-dotenv aiohttp dnspython pillow python-magic pyexiftool shodan
```

### Running the Bot
```bash
python main.py
```

<div align="center">

## [Join my discord server](https://discord.gg/2nHHHBWNDw)

</div>

## Command Reference

### Security Commands
- `/checkurl <url>` - Check a URL against multiple security services
- `/ip <ip>` - Get geolocation and network info for an IP address
- `/darturl <url>` - Check URL against DART Project databases
- `/dartuser <user_id>` - Check Discord user ID against DART Project
- `/dartstats` - Get DART Project database statistics
- `/cve <cve_id>` - Look up CVE vulnerability details

### Network Commands
- `/domain <domain>` - Perform full domain reconnaissance
- `/dns <domain>` - Enumerate DNS records for a domain
- `/ssl <domain>` - Check SSL/TLS configuration of a domain
- `/headers <url>` - Analyze HTTP security headers
- `/scan <ip>` - Perform a quick port scan (via Shodan)

### File Analysis
- `/metadata <url>` - Extract metadata from a file (supports images, PDFs, Office docs)

### URL Utilities
- `/unshorten <url>` - Follow URL redirects to reveal final destination

## API Requirements
The bot integrates with several external services that require API keys:
- VirusTotal
- URLScan.io
- IPInfo
- Shodan
- DART Project

## Project Structure
```
ToolBox-Bot/
├── commands/
│   ├── checkurl.py      # URL security checking
│   ├── cve.py           # CVE vulnerability lookup
│   ├── dart.py          # DART Project integration
│   ├── dns.py           # DNS enumeration
│   ├── domain.py        # Domain reconnaissance
│   ├── headers.py       # HTTP headers analysis
│   ├── ip.py            # IP geolocation
│   ├── metadata.py      # File metadata extraction
│   ├── scan.py          # Port scanning
│   ├── ssl.py           # SSL/TLS checking
│   └── unshorten.py     # URL unshortening
├── utils/
│   └── url_checker.py   # URL checking service integration
├── main.py              # Bot entry point
└── .env                 # Configuration file
```

## Contributing
Contributions are welcome! Please fork the repository and submit pull requests for new features or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.