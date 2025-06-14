import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

class ToolBoxBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True

        super().__init__(command_prefix="!", intents=intents, help_command=None)

    # Load all command modules
    async def setup_hook(self):
        loaded = []
        for filename in os.listdir("./commands"):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = f"commands.{filename[:-3]}"
                try:
                    await self.load_extension(module_name)
                    loaded.append(module_name)
                    logging.info(f"Successfully loaded: {module_name}")
                except Exception as e:
                    logging.error(f"Failed to load {module_name}: {e}")

        await self.tree.sync()
        logging.info("Commands synced with Discord")

    async def on_ready(self):
        logging.info(f"{self.user} has connected to Discord!")
        logging.info(f"Bot is ready and serving {len(self.guilds)} guilds")

        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching, name="for suspicious URLs 🔍"
        )
        await self.change_presence(activity=activity)


async def main():
    bot = ToolBoxBot()

    try:
        await bot.start(os.getenv("DISCORD_TOKEN"))
    except Exception as e:
        logging.error(f"Error starting bot: {e}")


if __name__ == "__main__":
    asyncio.run(main())
