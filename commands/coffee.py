import discord
from discord.ext import commands
from discord import app_commands
import logging
import random


class CoffeeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Coffee GIFs collection
        self.coffee_gifs = [
            "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExeW9peTI3cG1laDRqeTN4N28xaHpoandyeWUxemVweWd2aG85enl2dSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/J67PfTvmtCyWn7MOUF/giphy.gif",
            "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExdjVmMm91cWQ5Ym9wN3Rnc3NnbTQxN3duZmE5cDEyN3Ribmwxcjk3NyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/6H4JhdlQ3wUCc38OZ0/giphy.gif",
            "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExdmJoMWZ5ZmNrZGFyZnpyMmJidTh5aHh0aXRnZ3QzOTJ6aHFicHNiayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/2xNDxiZaUj1kY/giphy.gif",
            "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExNm9uODZhN21yY3g3amtzaTgyNmJjZmloajJtbGsyeGlvZmNob3A0OCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/cC2YPER2ne7B840cSK/giphy.gif",
            "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHdzeG5ybDN5aG1td2MweXl0bHBlYm5sYjhhM3F5amRuNHU2cmNuMSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Wn74RUT0vjnoU98Hnt/giphy.gif",
            "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExeHN2amt4bG95eWpmOGoyNzFpZGdjbWMydnoybWlyYTN6cmx6NGd3ayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/nPd1Qc3WMM2Jcs7uVp/giphy.gif",
            "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExNzlwN3loZ2xhOHNiczBxY2tyMGd5dzFhZmJzYzl1MnV3Z3NqZWNtOCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/4TdO2Viv7Z1TB0FHgv/giphy.gif",
            "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExajg1YW5vZ2ZkNDRxdGluZ2pqMnk5dmZ4eXI0YmV3bWJpc2NocWdlNCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Mk1wQ8cH5TtsqafLiX/giphy.gif",
            "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTJoMXZvZ3pidHNmd2k0Znpub2FhdTQ1c2libTFkdWtpZ2x2empvZyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/t06x4H3AeuowbhdZFU/giphy.gif",
            "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExb2F2NHZqNWprODdrZ2thaGxiNzBkOTRua3NtbzFzczgxd2E2M2JsdSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/K3htdZ1XuVWVD5DZDZ/giphy.gif",
            "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExOWx3YXJoeXFsanQ3MDRnNnAxaXRwbjEyNWNqNjh1djJhN216MnBpMiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/JvvLdUb6iVk1YiN7pn/giphy.gif",
            "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExOGdlM2RzbnpuY3M5cGFuM3BuazVxYXE3Nmpjd2thdThqMXJndHV1bCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3oriO04qxVReM5rJEA/giphy.gif",
            "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZzI3MjRyNGdpMWxrMDhxN2Zha2tkcDEyNjB2ZHU1Y2xzaThyYzZ6YiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/DrJm6F9poo4aA/giphy.gif",
            "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExNmIya3d5cWgyZWt2Z3N0bm8zZnE1ZnYwcGhncjJ1eXE0czZkMjYxbCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/ceeFbVxiZzMBi/giphy.gif",
            "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZW50enBpejk2N2R2MndibGFqeGF5bHp2djNlcThhenU0Y3VtNHNkZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/koTAN2V1PTOzC/giphy.gif",
            "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExZTExZnRlajY0Nm5nMWVxaXQyMGJqbHVqa3g4NmJrYmZwa2szdjN3NyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/XEOdmFHVznCerkI6CI/giphy.gif",
            "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExa3VoMGU1ZXdoZzdxaWJidW5mdmxxOGg4NThyZnB6czZhZHg5Z2tpZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/AZQGMIiEK8yDfGEn55/giphy.gif",
            "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExanhmZmp4aXptcXkyZnhhaGh3bGRzZ2k4am5jdHNoMnY2am8yZDJ4bCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/wrIm25gJBAaX9P8BLQ/giphy.gif",
            "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExOHcwa3F4djlocmNmMm0xeWV6cjRxaW40dDR2eXoxdTVuaGN5ZmllYiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/nIJEp8gOiQq6EmL2cY/giphy.gif"
        ]

        # Random descriptions for the embed
        self.coffee_descriptions = [
            "*Ahh, that's the good stuff* ☕",
            "*First sip of the day hits different* ☕",
            "*Liquid motivation in progress...* ☕",
            "*Brain.exe loading... please wait* ☕",
            "*Converting coffee to code...* ☕",
            "*Caffeinating for maximum productivity* ☕",
            "*This is how legends are fueled* ☕",
            "*Warning: Human powered by coffee* ☕",
            "*Sip by sip, bug by bug* ☕",
            "*Coffee: Because sleep is for the weak* ☕",
            "*Debugging life, one cup at a time* ☕",
            "*May your coffee be strong and your Wi-Fi stronger* ☕",
            "*Running on coffee and determination* ☕",
            "*Espresso yourself* ☕",
            "*Coffee: The most important commit of the day* ☕"
        ]

        # Random footer texts
        self.coffee_footers = [
            "Perfect fuel for coding sessions ⚡",
            "Powered by caffeine and dreams ✨",
            "One cup closer to enlightenment 🧘",
            "The secret ingredient to all great code 💻",
            "Brewing up some productivity 🚀",
            "Coffee: Because adulting is hard ☕",
            "Turning coffee into features since day one 🔧",
            "May the grind be with you ⚡",
            "Caffeine: A developer's best friend 💙",
            "Life's too short for bad coffee ☕",
            "Fueling the next big idea 💡",
            "Coffee break = creative breakthrough 🎨",
            "The pause that refreshes (and debugs) 🔄",
            "Brewing excellence, one sip at a time 🏆",
            "Coffee: The original energy drink ⚡"
        ]

    # Get a random coffee GIF
    def get_random_coffee_gif(self):
        return random.choice(self.coffee_gifs)

    # Get a random description
    def get_random_description(self):
        return random.choice(self.coffee_descriptions)

    # Get a random footer text
    def get_random_footer(self):
        return random.choice(self.coffee_footers)

    @app_commands.command(
        name="coffee",
        description="☕ Take a coffee break with a random coffee GIF"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def coffee(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            # Get random content
            gif_url = self.get_random_coffee_gif()
            description = self.get_random_description()
            footer_text = self.get_random_footer()

            # Create embed
            embed = discord.Embed(
                title="☕ Coffee Break",
                color=0x8B4513,  # Coffee brown color
                description=description
            )

            embed.set_image(url=gif_url)
            embed.set_footer(text=footer_text)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error(f"Error in coffee command: {e}")

            # Fallback embed if everything fails
            fallback_embed = discord.Embed(
                title="☕ Sips coffee",
                color=0x8B4513,
                description="*Coffee machine is broken, but the intention is there* ☕"
            )

            try:
                await interaction.followup.send(embed=fallback_embed)
            except:
                await interaction.followup.send("☕ *sips coffee*")


async def setup(bot):
    await bot.add_cog(CoffeeCommand(bot))