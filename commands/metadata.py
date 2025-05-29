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
import mimetypes
import json
from datetime import datetime

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


class ImageMetadataCommand(commands.Cog):
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

        # Basic signature detection for images
        if file_content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        elif file_content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        elif file_content.startswith(b"GIF8"):
            return "image/gif"
        elif file_content.startswith(b"RIFF") and b"WEBP" in file_content[:12]:
            return "image/webp"
        elif file_content.startswith(b"BM"):
            return "image/bmp"
        elif file_content.startswith((b"II*\x00", b"MM\x00*")):
            return "image/tiff"

        return "application/octet-stream"

    def convert_gps_to_degrees(self, gps_coord, gps_coord_ref):
        """Convert GPS coordinates from degrees/minutes/seconds to decimal degrees"""
        try:
            if isinstance(gps_coord, (list, tuple)) and len(gps_coord) == 3:
                degrees = float(gps_coord[0])
                minutes = float(gps_coord[1])
                seconds = float(gps_coord[2])

                decimal_degrees = degrees + (minutes / 60.0) + (seconds / 3600.0)

                if gps_coord_ref in ['S', 'W']:
                    decimal_degrees = -decimal_degrees

                return decimal_degrees
        except:
            pass
        return None

    def format_exif_value(self, key, value):
        """Format EXIF values for better display"""
        try:
            # Handle bytes
            if isinstance(value, bytes):
                try:
                    return value.decode('utf-8', errors='ignore').strip('\x00')
                except:
                    return f"<bytes: {len(value)} bytes>"

            # Handle tuples/lists
            if isinstance(value, (tuple, list)):
                if len(value) == 1:
                    return str(value[0])
                elif len(value) == 2 and key in ['XResolution', 'YResolution', 'FocalLength']:
                    # Handle rational numbers
                    if value[1] != 0:
                        return f"{value[0] / value[1]:.2f}"
                return str(value)

            # Handle specific EXIF tags
            if key == 'DateTime' or key == 'DateTimeOriginal' or key == 'DateTimeDigitized':
                try:
                    dt = datetime.strptime(str(value), '%Y:%m:%d %H:%M:%S')
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    return str(value)

            # Handle orientation
            if key == 'Orientation':
                orientations = {
                    1: "Normal",
                    2: "Mirrored horizontal",
                    3: "Rotated 180°",
                    4: "Mirrored vertical",
                    5: "Mirrored horizontal, rotated 270°",
                    6: "Rotated 90°",
                    7: "Mirrored horizontal, rotated 90°",
                    8: "Rotated 270°"
                }
                return orientations.get(value, f"Unknown ({value})")

            # Handle flash
            if key == 'Flash':
                flash_modes = {
                    0: "No Flash",
                    1: "Flash",
                    5: "Flash, no strobe return",
                    7: "Flash, strobe return",
                    9: "Flash, compulsory",
                    13: "Flash, compulsory, no strobe return",
                    15: "Flash, compulsory, strobe return",
                    16: "No Flash, compulsory",
                    24: "No Flash, auto",
                    25: "Flash, auto",
                    29: "Flash, auto, no strobe return",
                    31: "Flash, auto, strobe return"
                }
                return flash_modes.get(value, f"Flash mode {value}")

            return str(value)
        except:
            return str(value)

    def extract_image_metadata(self, file_content):
        """Extract comprehensive metadata from image files"""
        try:
            image = Image.open(io.BytesIO(file_content))
            metadata = {}

            # Basic image info
            metadata["Format"] = image.format
            metadata["Mode"] = image.mode
            metadata["Size"] = f"{image.size[0]}x{image.size[1]} pixels"

            # Try to get color profile info
            if hasattr(image, 'info') and 'icc_profile' in image.info:
                metadata["ColorProfile"] = "Present"

            # Extract comprehensive EXIF data using the newer getexif() method
            try:
                exif_dict = image.getexif()
                if exif_dict:
                    gps_data = {}

                    for tag_id, value in exif_dict.items():
                        tag_name = TAGS.get(tag_id, f"Tag_{tag_id}")

                        # Handle GPS data specially
                        if tag_name == "GPSInfo":
                            gps_info = {}
                            for gps_tag_id, gps_value in value.items():
                                gps_tag_name = GPSTAGS.get(gps_tag_id, f"GPS_Tag_{gps_tag_id}")
                                gps_info[gps_tag_name] = gps_value

                            # Convert GPS coordinates to decimal degrees if possible
                            if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
                                decimal_lat = self.convert_gps_to_degrees(
                                    gps_info['GPSLatitude'],
                                    gps_info['GPSLatitudeRef']
                                )
                                if decimal_lat is not None:
                                    gps_info['GPSLatitudeDecimal'] = f"{decimal_lat:.6f}"

                            if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                                decimal_lon = self.convert_gps_to_degrees(
                                    gps_info['GPSLongitude'],
                                    gps_info['GPSLongitudeRef']
                                )
                                if decimal_lon is not None:
                                    gps_info['GPSLongitudeDecimal'] = f"{decimal_lon:.6f}"

                            # Add individual GPS fields to main metadata
                            for gps_key, gps_val in gps_info.items():
                                formatted_val = self.format_exif_value(gps_key, gps_val)
                                metadata[f"GPS_{gps_key}"] = formatted_val

                        else:
                            # Format and add regular EXIF data
                            formatted_value = self.format_exif_value(tag_name, value)
                            metadata[tag_name] = formatted_value

            except Exception as e:
                logging.debug(f"getexif() failed, trying _getexif(): {e}")

                # Fallback to older method
                if hasattr(image, '_getexif') and image._getexif() is not None:
                    exif_data = image._getexif()
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, f"Tag_{tag_id}")

                        if tag_name == "GPSInfo":
                            gps_info = {}
                            for gps_tag_id, gps_value in value.items():
                                gps_tag_name = GPSTAGS.get(gps_tag_id, f"GPS_Tag_{gps_tag_id}")
                                gps_info[gps_tag_name] = gps_value

                            for gps_key, gps_val in gps_info.items():
                                formatted_val = self.format_exif_value(gps_key, gps_val)
                                metadata[f"GPS_{gps_key}"] = formatted_val
                        else:
                            formatted_value = self.format_exif_value(tag_name, value)
                            metadata[tag_name] = formatted_value

            return metadata

        except Exception as e:
            logging.error(f"PIL metadata extraction error: {e}")
            return None

    def extract_metadata_with_exiftool(self, file_content):
        """Extract metadata using ExifTool if available"""
        if not HAS_EXIFTOOL:
            return {}

        try:
            with exiftool.ExifTool() as et:
                # Get all metadata as JSON
                metadata_json = et.execute_json("-j", "-", stdin=file_content)
                if metadata_json and len(metadata_json) > 0:
                    return metadata_json[0]
        except Exception as e:
            logging.debug(f"ExifTool extraction failed: {e}")

        return {}

    def organize_metadata(self, pil_metadata, exiftool_metadata):
        """Combine and organize metadata from different sources"""
        organized = {
            "basic": {},
            "camera": {},
            "settings": {},
            "datetime": {},
            "gps": {},
            "software": {},
            "other": {}
        }

        # Process PIL metadata
        for key, value in pil_metadata.items():
            key_lower = key.lower()

            if key in ["Format", "Mode", "Size", "ColorProfile"]:
                organized["basic"][key] = value
            elif key.startswith("GPS_"):
                organized["gps"][key] = value
            elif key in ["Make", "Model", "LensModel", "LensMake"]:
                organized["camera"][key] = value
            elif key in ["ISO", "FNumber", "ExposureTime", "FocalLength", "WhiteBalance",
                         "Flash", "MeteringMode", "ExposureMode", "SceneCaptureType"]:
                organized["settings"][key] = value
            elif "date" in key_lower or "time" in key_lower:
                organized["datetime"][key] = value
            elif key in ["Software", "ProcessingSoftware", "Artist", "Copyright"]:
                organized["software"][key] = value
            else:
                organized["other"][key] = value

        # Add ExifTool data that PIL might have missed
        for key, value in exiftool_metadata.items():
            if key.startswith(("File:", "ExifTool:", "SourceFile")):
                continue

            # Clean up the key
            clean_key = key.split(":")[-1] if ":" in key else key

            # Don't override PIL data unless it's more detailed
            found_in_pil = any(clean_key in cat for cat in organized.values())
            if not found_in_pil:
                formatted_value = self.format_exif_value(clean_key, value)

                if any(term in clean_key.lower() for term in ["gps", "location", "latitude", "longitude"]):
                    organized["gps"][clean_key] = formatted_value
                elif any(term in clean_key.lower() for term in ["camera", "make", "model", "lens"]):
                    organized["camera"][clean_key] = formatted_value
                elif any(term in clean_key.lower() for term in ["iso", "aperture", "exposure", "focal", "flash"]):
                    organized["settings"][clean_key] = formatted_value
                elif any(term in clean_key.lower() for term in ["date", "time"]):
                    organized["datetime"][clean_key] = formatted_value
                elif any(term in clean_key.lower() for term in ["software", "application", "program"]):
                    organized["software"][clean_key] = formatted_value
                else:
                    organized["other"][clean_key] = formatted_value

        return organized

    @app_commands.command(name="metadata", description="Extract comprehensive metadata from image files")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(url="URL to an image file (e.g., Discord attachment link)")
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
                        if content_length and int(content_length) > 50 * 1024 * 1024:  # 50MB limit
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

                        # Check if this is an image file
                        if not file_type.startswith("image/"):
                            await interaction.followup.send(
                                f"File type `{file_type}` is not supported.\n"
                                f"This command only works with image files (JPEG, PNG, GIF, WEBP, BMP, TIFF)."
                            )
                            return

                        # Extract metadata using PIL
                        pil_metadata = await asyncio.to_thread(
                            self.extract_image_metadata, file_content
                        )

                        if not pil_metadata:
                            await interaction.followup.send(
                                "No metadata could be extracted from this image"
                            )
                            return

                        # Extract metadata using ExifTool if available
                        exiftool_metadata = {}
                        if HAS_EXIFTOOL:
                            exiftool_metadata = await asyncio.to_thread(
                                self.extract_metadata_with_exiftool, file_content
                            )

                        # Organize metadata
                        organized_metadata = self.organize_metadata(pil_metadata, exiftool_metadata)

                        # Create embeds (Discord has a limit of 6000 characters per embed)
                        embeds = []

                        # Main embed with basic info and file details
                        main_embed = discord.Embed(
                            title="📸 Image Metadata Analysis",
                            description=f"**File:** `{filename}`\n**Type:** `{file_type}`",
                            color=0x3498DB
                        )

                        # Add basic information
                        if organized_metadata["basic"]:
                            basic_lines = []
                            for key, value in organized_metadata["basic"].items():
                                basic_lines.append(f"• **{key}**: {value}")
                            main_embed.add_field(
                                name="📋 Basic Information",
                                value="\n".join(basic_lines),
                                inline=False
                            )

                        # Add camera information
                        if organized_metadata["camera"]:
                            camera_lines = []
                            for key, value in organized_metadata["camera"].items():
                                camera_lines.append(f"• **{key}**: {value}")
                            main_embed.add_field(
                                name="📷 Camera Information",
                                value="\n".join(camera_lines[:10]),  # Limit to prevent overflow
                                inline=False
                            )

                        # Add camera settings
                        if organized_metadata["settings"]:
                            settings_lines = []
                            for key, value in organized_metadata["settings"].items():
                                settings_lines.append(f"• **{key}**: {value}")
                            main_embed.add_field(
                                name="⚙️ Camera Settings",
                                value="\n".join(settings_lines[:10]),
                                inline=False
                            )

                        embeds.append(main_embed)

                        # Create second embed for datetime and software info
                        if organized_metadata["datetime"] or organized_metadata["software"]:
                            info_embed = discord.Embed(
                                title="📅 Additional Information",
                                color=0x3498DB
                            )

                            if organized_metadata["datetime"]:
                                datetime_lines = []
                                for key, value in organized_metadata["datetime"].items():
                                    datetime_lines.append(f"• **{key}**: {value}")
                                info_embed.add_field(
                                    name="📅 Date & Time Information",
                                    value="\n".join(datetime_lines),
                                    inline=False
                                )

                            if organized_metadata["software"]:
                                software_lines = []
                                for key, value in organized_metadata["software"].items():
                                    software_lines.append(f"• **{key}**: {value}")
                                info_embed.add_field(
                                    name="💻 Software Information",
                                    value="\n".join(software_lines),
                                    inline=False
                                )

                            embeds.append(info_embed)

                        # Create GPS embed with warning if GPS data found
                        if organized_metadata["gps"]:
                            gps_embed = discord.Embed(
                                title="⚠️ GPS Location Data Found",
                                description="**Privacy Warning**: This image contains location information!",
                                color=0xFF6B35  # Orange color for warning
                            )

                            gps_lines = []
                            for key, value in organized_metadata["gps"].items():
                                gps_lines.append(f"• **{key}**: {value}")

                            gps_embed.add_field(
                                name="🌍 GPS Information",
                                value="\n".join(gps_lines),
                                inline=False
                            )

                            embeds.append(gps_embed)

                        # Create other metadata embed
                        if organized_metadata["other"]:
                            other_embed = discord.Embed(
                                title="📝 Other Metadata",
                                color=0x3498DB
                            )

                            other_lines = []
                            count = 0
                            for key, value in organized_metadata["other"].items():
                                if count >= 20:  # Limit to prevent Discord limits
                                    other_lines.append("• *... and more (truncated)*")
                                    break
                                other_lines.append(f"• **{key}**: {value}")
                                count += 1

                            if other_lines:
                                other_embed.add_field(
                                    name="Additional Fields",
                                    value="\n".join(other_lines),
                                    inline=False
                                )
                                embeds.append(other_embed)

                        # Add footer to last embed
                        if embeds:
                            tools_used = ["PIL (Pillow)"]
                            if HAS_MAGIC:
                                tools_used.append("python-magic")
                            if HAS_EXIFTOOL:
                                tools_used.append("ExifTool")

                            embeds[-1].set_footer(
                                text=f"File size: {len(file_content):,} bytes • Tools: {', '.join(tools_used)}"
                            )

                        # Send embeds (Discord allows up to 10 embeds per message)
                        if embeds:
                            await interaction.followup.send(embeds=embeds[:10])
                        else:
                            await interaction.followup.send("No displayable metadata found in this image")

                except asyncio.TimeoutError:
                    await interaction.followup.send(
                        "Request timed out. Please try a smaller file or different URL."
                    )
                except Exception as e:
                    logging.error(f"Error processing file: {e}")
                    await interaction.followup.send(f"Error processing image: {str(e)}")

        except Exception as e:
            logging.error(f"Error in metadata command: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An unexpected error occurred.", ephemeral=True
                )
            else:
                await interaction.followup.send("An unexpected error occurred.")


async def setup(bot):
    await bot.add_cog(ImageMetadataCommand(bot))