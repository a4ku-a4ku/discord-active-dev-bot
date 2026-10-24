import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BOT_OWNER_ID = os.getenv("BOT_OWNER_ID", "").strip()

intents = discord.Intents.default()

class BadgeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        print("Registering and syncing slash command (/activedev)...")
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s) with Discord.")
        except Exception as e:
            print(f"Error syncing commands: {e}")

bot = BadgeBot()

@bot.event
async def on_ready():
    print("=" * 60)
    print(f"Logged in as: {bot.user.name} ({bot.user.id})")
    print("Bot is ready for Active Developer Badge qualification!")
    print("Use '/activedev' in your Discord server.")
    print("=" * 60)

@bot.tree.command(
    name="activedev",
    description="Active Developer Badge command - Restricted to Bot Owner / Server Owner"
)
async def activedev(interaction: discord.Interaction):
    user_id = interaction.user.id
    is_owner = False

    # 1. Check explicit BOT_OWNER_ID from .env
    if BOT_OWNER_ID and BOT_OWNER_ID.isdigit() and user_id == int(BOT_OWNER_ID):
        is_owner = True

    # 2. Check Discord Application Owner / Team
    if not is_owner:
        try:
            app_info = await bot.application_info()
            if app_info.team:
                is_owner = any(member.id == user_id for member in app_info.team.members)
            elif app_info.owner:
                is_owner = (user_id == app_info.owner.id)
        except Exception as err:
            print(f"Application info check warning: {err}")

    # 3. Check Server Owner (if executed inside a Discord Server)
    if not is_owner and interaction.guild and interaction.guild.owner_id == user_id:
        is_owner = True

    # Access control check
    if not is_owner:
        await interaction.response.send_message(
            "❌ **Access Denied**: Only the **Bot Owner** or **Server Owner** can run this command.",
            ephemeral=True
        )
        return

    # Success Response
    embed = discord.Embed(
        title="🌟 Active Developer Command Executed!",
        description=(
            f"Congratulations **{interaction.user.name}**!\n\n"
            "Discord has registered this application command.\n\n"
            "📌 **How to claim your badge:**\n"
            "1. Discord checks commands on a rolling basis (can take **up to 24 hours**).\n"
            "2. Ensure your bot is installed in a server with **Community enabled** (Server Settings -> Enable Community).\n"
            "3. Go to [Discord Active Developer Portal](https://discord.com/developers/active-developer) to claim your badge."
        ),
        color=discord.Color.brand_green()
    )
    embed.add_field(name="Bot Name", value=bot.user.name, inline=True)
    embed.add_field(name="User ID", value=str(user_id), inline=True)
    embed.set_footer(text="Discord Active Developer Badge")

    await interaction.response.send_message(embed=embed)
    print(f"[Slash Command] /activedev executed by authorized owner: {interaction.user.name} ({user_id})")

if __name__ == "__main__":
    if not TOKEN or TOKEN.startswith("YOUR_"):
        print("ERROR: DISCORD_BOT_TOKEN is missing or not configured in .env!")
    else:
        bot.run(TOKEN)
