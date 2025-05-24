import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from urllib.parse import urlparse
import magic
import io
import exiftool


class MetadataCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def extract_metadata(self, file_content, filename):
        try:
            with exiftool.ExifTool() as et:
                metadata = et.get_metadata_bytes(file_content)
                return metadata
        except Exception as e:
            logging.error(f"Metadata extraction error: {e}")
            return None

    @app_commands.command(name="metadata", description="Extract metadata from a file")
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
                    async with session.get(url) as response:
                        if response.status != 200:
                            await interaction.followup.send(
                                f"Failed to download file: HTTP {response.status}"
                            )
                            return

                        # Get filename from URL or Content-Disposition
                        filename = urlparse(url).path.split("/")[-1] or "unknown_file"
                        content_type = response.headers.get("Content-Type", "")

                        # Check if this is a supported file type
                        supported_types = [
                            "image/",
                            "application/pdf",
                            "application/msword",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "application/vnd.ms-excel",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "application/vnd.ms-powerpoint",
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        ]

                        if not any(t in content_type for t in supported_types):
                            await interaction.followup.send(
                                "File type not supported for metadata extraction"
                            )
                            return

                        # Download file content
                        file_content = await response.read()

                        # Extract metadata
                        metadata = await asyncio.to_thread(
                            self.extract_metadata, file_content, filename
                        )

                        if not metadata:
                            await interaction.followup.send(
                                "Failed to extract metadata from file"
                            )
                            return

                        # Create embed with important metadata
                        embed = discord.Embed(
                            title=f"📄 Metadata for {filename}", color=0x3498DB
                        )

                        # Add important fields
                        important_fields = [
                            "File:FileName",
                            "File:FileSize",
                            "File:FileType",
                            "EXIF:CreateDate",
                            "EXIF:ModifyDate",
                            "EXIF:Software",
                            "PDF:Author",
                            "PDF:Creator",
                            "PDF:Producer",
                            "XMP:CreatorTool",
                            "XMP:HistorySoftwareAgent",
                            "IPTC:By-line",
                            "IPTC:CopyrightNotice",
                        ]

                        found_fields = []
                        for field in important_fields:
                            if field in metadata:
                                value = str(metadata[field])[:100]  # Limit length
                                found_fields.append(
                                    f"• **{field.split(':')[-1]}**: {value}"
                                )

                        if found_fields:
                            embed.add_field(
                                name="Extracted Metadata",
                                value="\n".join(
                                    found_fields[:10]
                                ),  # Limit to 10 fields
                                inline=False,
                            )

                        # Check for GPS coordinates
                        gps_fields = [
                            "EXIF:GPSLatitude",
                            "EXIF:GPSLongitude",
                            "XMP:GPSLatitude",
                            "XMP:GPSLongitude",
                        ]

                        gps_data = []
                        for field in gps_fields:
                            if field in metadata:
                                gps_data.append(
                                    f"• **{field.split(':')[-1]}**: {metadata[field]}"
                                )

                        if gps_data:
                            embed.add_field(
                                name="⚠️ GPS Location Data",
                                value="\n".join(gps_data),
                                inline=False,
                            )
                            embed.color = 0xFF0000

                        embed.set_footer(
                            text="Some metadata may have been truncated for display"
                        )

                        await interaction.followup.send(embed=embed)

                except Exception as e:
                    await interaction.followup.send(f"Error processing file: {str(e)}")

        except Exception as e:
            logging.error(f"Error in metadata command: {e}")
            await interaction.followup.send("An unexpected error occurred.")


async def setup(bot):
    await bot.add_cog(MetadataCommand(bot))
