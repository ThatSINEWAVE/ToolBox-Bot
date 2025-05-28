import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from urllib.parse import urlparse
import io
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import struct
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
import mimetypes
import hashlib
import os
import platform

# Try to import optional dependencies
try:
    import magic

    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    logging.warning("python-magic not available, using basic file type detection")

try:
    import exiftool

    HAS_EXIFTOOL = True
except ImportError:
    HAS_EXIFTOOL = False
    logging.warning("exiftool not available, using built-in metadata extraction")


class MetadataCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def detect_file_type(self, file_content, filename):
        """Detect file type using multiple methods"""
        # First try python-magic if available
        if HAS_MAGIC:
            try:
                mime_type = magic.from_buffer(file_content, mime=True)
                return mime_type
            except Exception as e:
                logging.warning(f"Magic detection failed: {e}")

        # Fallback to mimetypes based on filename
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            return mime_type

        # Basic signature detection
        if file_content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        elif file_content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        elif file_content.startswith(b"GIF8"):
            return "image/gif"
        elif file_content.startswith(b"%PDF"):
            return "application/pdf"
        elif file_content.startswith(b"PK\x03\x04"):
            return "application/zip"  # Could be Office document

        return "application/octet-stream"

    def extract_image_metadata(self, file_content):
        """Extract metadata from image files using PIL"""
        try:
            image = Image.open(io.BytesIO(file_content))
            metadata = {}

            # Basic image info
            metadata["Format"] = image.format
            metadata["Mode"] = image.mode
            metadata["Size"] = f"{image.size[0]}x{image.size[1]}"

            # Extract EXIF data
            if hasattr(image, "_getexif") and image._getexif() is not None:
                exif_data = image._getexif()
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)

                    # Handle GPS data specially
                    if tag == "GPSInfo":
                        gps_data = {}
                        for gps_tag_id, gps_value in value.items():
                            gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            gps_data[gps_tag] = gps_value
                        metadata["GPS"] = gps_data
                    else:
                        # Convert bytes to string if needed
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8")
                            except:
                                value = str(value)
                        metadata[tag] = value

            return metadata
        except Exception as e:
            logging.error(f"PIL metadata extraction error: {e}")
            return None

    def extract_office_metadata(self, file_content):
        """Extract metadata from Office documents (docx, xlsx, pptx)"""
        try:
            with zipfile.ZipFile(io.BytesIO(file_content), "r") as zip_file:
                metadata = {}

                # Try to read core properties
                try:
                    core_props = zip_file.read("docProps/core.xml")
                    root = ET.fromstring(core_props)

                    # Define namespaces
                    namespaces = {
                        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
                        "dc": "http://purl.org/dc/elements/1.1/",
                        "dcterms": "http://purl.org/dc/terms/",
                        "dcmitype": "http://purl.org/dc/dcmitype/",
                        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
                    }

                    # Extract common properties
                    props_map = {
                        "dc:creator": "Author",
                        "cp:lastModifiedBy": "LastModifiedBy",
                        "dcterms:created": "Created",
                        "dcterms:modified": "Modified",
                        "cp:revision": "Revision",
                        "dc:title": "Title",
                        "dc:subject": "Subject",
                        "cp:category": "Category",
                        "cp:keywords": "Keywords",
                    }

                    for xpath, name in props_map.items():
                        elements = root.findall(f".//{xpath}", namespaces)
                        if elements:
                            metadata[name] = elements[0].text

                except Exception as e:
                    logging.debug(f"Core properties extraction failed: {e}")

                # Try to read app properties
                try:
                    app_props = zip_file.read("docProps/app.xml")
                    root = ET.fromstring(app_props)

                    app_props_map = {
                        "Application": "Application",
                        "AppVersion": "AppVersion",
                        "Company": "Company",
                        "TotalTime": "TotalEditTime",
                    }

                    for prop, name in app_props_map.items():
                        elements = root.findall(f".//{prop}")
                        if elements:
                            metadata[name] = elements[0].text

                except Exception as e:
                    logging.debug(f"App properties extraction failed: {e}")

                return metadata if metadata else None

        except Exception as e:
            logging.error(f"Office metadata extraction error: {e}")
            return None

    def extract_pdf_metadata(self, file_content):
        """Basic PDF metadata extraction"""
        try:
            # Look for PDF info dictionary
            content_str = file_content.decode("latin-1", errors="ignore")
            metadata = {}

            # Find info object
            if "/Info" in content_str:
                # This is a very basic implementation
                # In production, you'd want to use a proper PDF library like PyPDF2
                info_start = content_str.find("/Info")
                info_section = content_str[info_start : info_start + 1000]

                # Look for common metadata fields
                fields = [
                    "Title",
                    "Author",
                    "Subject",
                    "Creator",
                    "Producer",
                    "CreationDate",
                    "ModDate",
                ]
                for field in fields:
                    pattern = f"/{field}"
                    if pattern in info_section:
                        start = info_section.find(pattern)
                        if start != -1:
                            # Extract value (simplified)
                            line_end = info_section.find("\n", start)
                            if line_end != -1:
                                value = (
                                    info_section[start:line_end]
                                    .split("(")[-1]
                                    .split(")")[0]
                                )
                                if value:
                                    metadata[field] = value

            return metadata if metadata else None
        except Exception as e:
            logging.error(f"PDF metadata extraction error: {e}")
            return None

    def extract_metadata(self, file_content, filename, file_type):
        """Extract metadata based on file type - SYNCHRONOUS function"""
        metadata = {}

        # Basic file info
        metadata["FileSize"] = f"{len(file_content):,} bytes"
        metadata["FileType"] = file_type

        try:
            if file_type.startswith("image/"):
                image_meta = self.extract_image_metadata(file_content)
                if image_meta:
                    metadata.update(image_meta)

            elif "officedocument" in file_type or file_type in [
                "application/vnd.ms-word",
                "application/vnd.ms-excel",
                "application/vnd.ms-powerpoint",
            ]:
                office_meta = self.extract_office_metadata(file_content)
                if office_meta:
                    metadata.update(office_meta)

            elif file_type == "application/pdf":
                pdf_meta = self.extract_pdf_metadata(file_content)
                if pdf_meta:
                    metadata.update(pdf_meta)

            # If exiftool is available, try that as well for additional data
            if HAS_EXIFTOOL:
                try:
                    with exiftool.ExifTool() as et:
                        exif_meta = et.get_metadata_bytes(file_content)
                        if exif_meta:
                            # Add selected exiftool data
                            for key, value in exif_meta.items():
                                if not key.startswith("File:") or key in [
                                    "File:FileName",
                                    "File:Directory",
                                ]:
                                    continue
                                clean_key = key.split(":")[-1]
                                if clean_key not in metadata:
                                    metadata[clean_key] = value
                except Exception as e:
                    logging.debug(f"ExifTool extraction failed: {e}")

            return metadata

        except Exception as e:
            logging.error(f"Metadata extraction error: {e}")
            return metadata  # Return basic metadata even if advanced extraction fails

    @app_commands.command(name="metadata", description="Extract metadata from a file")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="URL to a file (e.g., Discord attachment link)")
    async def metadata(self, interaction: discord.Interaction, url: str):
        try:
            if not url.startswith(("http://", "https://")):
                await interaction.response.send_message(
                    "Please provide a valid URL", ephemeral=True
                )
                return

            await interaction.response.defer()

            async with aiohttp.ClientSession() as session:
                try:
                    # Set reasonable timeout and size limits
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with session.get(url, timeout=timeout) as response:
                        if response.status != 200:
                            await interaction.followup.send(
                                f"Failed to download file: HTTP {response.status}"
                            )
                            return

                        # Check content length
                        content_length = response.headers.get("Content-Length")
                        if (
                            content_length and int(content_length) > 50 * 1024 * 1024
                        ):  # 50MB limit
                            await interaction.followup.send(
                                "File too large (>50MB). Please use a smaller file."
                            )
                            return

                        # Get filename from URL or Content-Disposition header
                        filename = urlparse(url).path.split("/")[-1] or "unknown_file"
                        if "Content-Disposition" in response.headers:
                            cd = response.headers["Content-Disposition"]
                            if "filename=" in cd:
                                filename = cd.split("filename=")[-1].strip('"')

                        # Download file content
                        file_content = await response.read()

                        # Detect file type
                        file_type = self.detect_file_type(file_content, filename)

                        # Check if this is a supported file type
                        supported_types = [
                            "image/",
                            "application/pdf",
                            "application/msword",
                            "application/vnd.openxmlformats-officedocument",
                            "application/vnd.ms-excel",
                            "application/vnd.ms-powerpoint",
                        ]

                        if not any(t in file_type for t in supported_types):
                            await interaction.followup.send(
                                f"File type `{file_type}` not supported for metadata extraction.\n"
                                f"Supported types: Images, PDF, Office documents"
                            )
                            return

                        # Extract metadata - NOW PROPERLY CALLING THE SYNC FUNCTION IN A THREAD
                        metadata = await asyncio.to_thread(
                            self.extract_metadata, file_content, filename, file_type
                        )

                        if not metadata:
                            await interaction.followup.send(
                                "No metadata could be extracted from this file"
                            )
                            return

                        # Create embed with metadata
                        embed = discord.Embed(
                            title=f"📄 Metadata Analysis",
                            description=f"**File:** `{filename}`",
                            color=0x3498DB,
                        )

                        # Organize metadata into categories
                        basic_info = []
                        creation_info = []
                        location_info = []
                        software_info = []
                        other_info = []

                        for key, value in metadata.items():
                            if isinstance(value, dict):
                                continue  # Skip complex nested data for now

                            value_str = str(value)[:100]  # Limit length
                            formatted_line = f"• **{key}**: {value_str}"

                            # Categorize metadata
                            if key.lower() in [
                                "filesize",
                                "filetype",
                                "format",
                                "mode",
                                "size",
                            ]:
                                basic_info.append(formatted_line)
                            elif (
                                "date" in key.lower()
                                or "time" in key.lower()
                                or key.lower()
                                in ["created", "modified", "creationdate", "moddate"]
                            ):
                                creation_info.append(formatted_line)
                            elif (
                                "gps" in key.lower()
                                or "location" in key.lower()
                                or "latitude" in key.lower()
                                or "longitude" in key.lower()
                            ):
                                location_info.append(formatted_line)
                            elif key.lower() in [
                                "software",
                                "application",
                                "creator",
                                "producer",
                                "appversion",
                                "make",
                                "model",
                            ]:
                                software_info.append(formatted_line)
                            else:
                                other_info.append(formatted_line)

                        # Add fields to embed
                        if basic_info:
                            embed.add_field(
                                name="📋 Basic Information",
                                value="\n".join(basic_info[:5]),
                                inline=False,
                            )

                        if creation_info:
                            embed.add_field(
                                name="📅 Creation Information",
                                value="\n".join(creation_info[:5]),
                                inline=False,
                            )

                        if software_info:
                            embed.add_field(
                                name="💻 Software Information",
                                value="\n".join(software_info[:5]),
                                inline=False,
                            )

                        # Handle GPS/Location data specially
                        gps_found = False
                        if "GPS" in metadata and isinstance(metadata["GPS"], dict):
                            gps_data = metadata["GPS"]
                            gps_lines = []
                            for gps_key, gps_value in gps_data.items():
                                if gps_key in [
                                    "GPSLatitude",
                                    "GPSLongitude",
                                    "GPSLatitudeRef",
                                    "GPSLongitudeRef",
                                ]:
                                    gps_lines.append(f"• **{gps_key}**: {gps_value}")
                                    gps_found = True

                            if gps_lines:
                                embed.add_field(
                                    name="⚠️ GPS Location Data Found",
                                    value="\n".join(gps_lines),
                                    inline=False,
                                )

                        if location_info or gps_found:
                            embed.color = 0xFF6B35  # Orange color for privacy warning

                        if other_info:
                            embed.add_field(
                                name="📝 Additional Information",
                                value="\n".join(other_info[:5]),
                                inline=False,
                            )

                        # Add footer with tool info
                        tools_used = ["Built-in extractors"]
                        if HAS_MAGIC:
                            tools_used.append("python-magic")
                        if HAS_EXIFTOOL:
                            tools_used.append("ExifTool")

                        embed.set_footer(
                            text=f"Tools: {', '.join(tools_used)} • Some data may be truncated"
                        )

                        await interaction.followup.send(embed=embed)

                except asyncio.TimeoutError:
                    await interaction.followup.send(
                        "Request timed out. Please try a smaller file or different URL."
                    )
                except Exception as e:
                    logging.error(f"Error processing file: {e}")
                    await interaction.followup.send(f"Error processing file: {str(e)}")

        except Exception as e:
            logging.error(f"Error in metadata command: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An unexpected error occurred.", ephemeral=True
                )
            else:
                await interaction.followup.send("An unexpected error occurred.")


async def setup(bot):
    await bot.add_cog(MetadataCommand(bot))
