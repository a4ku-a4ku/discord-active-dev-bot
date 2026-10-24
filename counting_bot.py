import os
import json
import time
import asyncio
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from aiohttp import web

# Load configuration from .env file
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "316391521157120012"))
SLOWMODE_SECONDS = int(os.getenv("SLOWMODE_SECONDS", "30"))
BOT_OWNER_ID = os.getenv("BOT_OWNER_ID", "272861288265285632").strip()
PORT = int(os.getenv("PORT", "10000"))

# State file path
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "badge_state.json")

def load_badge_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_executed_at": 0.0,
        "last_executed_by": None,
        "reminded_29_days": False
    }

def save_badge_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[Error] Failed to save badge_state.json: {e}")

# Set up Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

class DevBadgeAndCountingBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.last_sent_timestamp = 0
        self.lock = asyncio.Lock()
        self.badge_state = load_badge_state()

    async def setup_hook(self):
        """Sync slash commands both instantly to the target guild and globally."""
        print("Registering and syncing slash commands with Discord...")
        try:
            # 1. Instant sync to target guild (appears immediately in server)
            guild_obj = discord.Object(id=TARGET_CHANNEL_ID)
            self.tree.copy_global_to(guild=guild_obj)
            synced_guild = await self.tree.sync(guild=guild_obj)
            print(f"Instantly synced {len(synced_guild)} slash command(s) to guild {TARGET_CHANNEL_ID}!")

            # 2. Global sync (propagates across Discord)
            synced_global = await self.tree.sync()
            print(f"Synced {len(synced_global)} global slash command(s).")
        except Exception as e:
            print(f"Failed to sync slash commands: {e}")

        # Start 29-day reminder background task loop
        self.badge_reminder_loop.start()

    @tasks.loop(hours=1)
    async def badge_reminder_loop(self):
        """Checks every hour if 29 days have passed since /activedev was last executed."""
        last_exec = self.badge_state.get("last_executed_at", 0)
        if last_exec <= 0:
            return  # No execution recorded yet

        elapsed_seconds = time.time() - last_exec
        days_elapsed = elapsed_seconds / 86400

        # Trigger warning at 29 days (between 29 and 30 days) if not already reminded
        if days_elapsed >= 29 and not self.badge_state.get("reminded_29_days", False):
            print(f"[Alert] 29 days have passed ({days_elapsed:.1f} days). Sending reminder...")
            target_channel = self.get_channel(TARGET_CHANNEL_ID)
            if target_channel:
                owner_mention = f"<@{BOT_OWNER_ID}>" if BOT_OWNER_ID else "Bot Owner"
                embed = discord.Embed(
                    title="⚠️ URGENT: Active Developer Badge Expiring Soon!",
                    description=(
                        f"Hey {owner_mention}!\n\n"
                        f"It has been **{int(days_elapsed)} days** since `/activedev` was last executed.\n\n"
                        "Discord requires at least **one slash command every 30 days** to keep your Active Developer Badge active!\n\n"
                        "👉 **Action Required**: Please run `/activedev` in this server right now to reset the 30-day countdown!"
                    ),
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Time Left", value="Less than 24 hours!", inline=True)
                embed.add_field(name="Command", value="`/activedev`", inline=True)
                embed.set_footer(text="Automated 29-Day Badge Reminder")

                try:
                    await target_channel.send(content=owner_mention, embed=embed)
                    self.badge_state["reminded_29_days"] = True
                    save_badge_state(self.badge_state)
                    print("[Alert] 29-day expiration reminder successfully sent to Discord channel!")
                except Exception as err:
                    print(f"[Error] Failed to send reminder to target channel: {err}")

    @badge_reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.wait_until_ready()

bot = DevBadgeAndCountingBot()

# =====================================================================
# SLASH COMMAND: /activedev (Restricted to Bot Owner or Server Owner)
# =====================================================================
@bot.tree.command(
    name="activedev",
    description="Trigger an application command to qualify for/renew the Discord Active Developer Badge"
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
            print(f"[Warning] Could not fetch application info: {err}")

    # 3. Check Server Owner (if executed inside a Discord Server / Guild)
    if not is_owner and interaction.guild and interaction.guild.owner_id == user_id:
        is_owner = True

    # Deny access if not the bot owner or server owner
    if not is_owner:
        await interaction.response.send_message(
            "❌ **Access Denied**: This command is restricted. Only the **Bot Owner** or **Server Owner** can use `/activedev`.",
            ephemeral=True
        )
        return

    # Update state
    now_ts = time.time()
    bot.badge_state["last_executed_at"] = now_ts
    bot.badge_state["last_executed_by"] = f"{interaction.user.name} ({user_id})"
    bot.badge_state["reminded_29_days"] = False
    save_badge_state(bot.badge_state)

    next_alert_date = datetime.fromtimestamp(now_ts + (29 * 86400), tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    # Success Response
    embed = discord.Embed(
        title="✨ Active Developer Command Executed!",
        description=(
            f"Hello **{interaction.user.name}**, your slash command ran successfully!\n\n"
            "**Status Details:**\n"
            "• **Discord Logging**: This slash command is now registered on Discord's servers.\n"
            "• **30-Day Badge Timer**: Reset successfully starting today.\n"
            f"• **Next 29-Day Reminder**: Scheduled for `{next_alert_date}` in <#{TARGET_CHANNEL_ID}>.\n\n"
            "📌 **Claiming your Badge**:\n"
            "If this is your first time, wait up to 24 hours and visit:\n"
            "[Discord Active Developer Portal](https://discord.com/developers/active-developer)"
        ),
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Bot Name", value=bot.user.name, inline=True)
    embed.add_field(name="Authorized User", value=f"<@{user_id}>", inline=True)
    embed.set_footer(text="Discord Active Developer Badge Helper")

    await interaction.response.send_message(embed=embed)
    print(f"[Badge Command] /activedev executed by {interaction.user.name} ({user_id}) at {datetime.now()}")

# =====================================================================
# SLASH COMMAND: /badgestatus (Check time remaining)
# =====================================================================
@bot.tree.command(
    name="badgestatus",
    description="Check the current status and time remaining for your Active Developer Badge"
)
async def badgestatus(interaction: discord.Interaction):
    last_exec = bot.badge_state.get("last_executed_at", 0)
    if last_exec <= 0:
        await interaction.response.send_message(
            "ℹ️ `/activedev` has not been run yet! Run `/activedev` now to start your 30-day Active Developer cycle.",
            ephemeral=True
        )
        return

    elapsed_seconds = time.time() - last_exec
    days_elapsed = elapsed_seconds / 86400
    days_left = max(0.0, 30.0 - days_elapsed)
    hours_left = max(0.0, (30.0 * 24.0) - (elapsed_seconds / 3600))
    days_until_warning = max(0.0, 29.0 - days_elapsed)

    embed = discord.Embed(
        title="📊 Active Developer Badge Status",
        color=discord.Color.blue() if days_left > 5 else discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Days Since Last Run", value=f"{days_elapsed:.1f} days", inline=True)
    embed.add_field(name="Time Until Expiration", value=f"{int(days_left)} days ({int(hours_left)} hours)", inline=True)
    embed.add_field(name="Time Until 29-Day Warning", value=f"{days_until_warning:.1f} days", inline=True)
    embed.add_field(name="Target Channel", value=f"<#{TARGET_CHANNEL_ID}>", inline=True)
    embed.add_field(name="Last Run By", value=str(bot.badge_state.get("last_executed_by", "Unknown")), inline=True)
    embed.set_footer(text="Run /activedev anytime to reset your 30-day countdown")

    await interaction.response.send_message(embed=embed)

# =====================================================================
# COUNTING BOT LOGIC
# =====================================================================
@bot.event
async def on_message(message: discord.Message):
    # Process text commands if any
    await bot.process_commands(message)

    # 1. Ignore messages from any other channel
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    # 2. Ignore messages sent by this bot itself
    if message.author.id == bot.user.id:
        return

    # 3. Validate content: only process clean digit-only messages
    raw_content = message.content.strip()
    if not raw_content.isdigit():
        return

    current_number = int(raw_content)
    next_number = current_number + 1

    # 4. Acquire async lock to handle messages sequentially
    async with bot.lock:
        elapsed = time.time() - bot.last_sent_timestamp
        if elapsed < SLOWMODE_SECONDS:
            wait_time = SLOWMODE_SECONDS - elapsed
            print(f"[Slowmode] Waiting {wait_time:.1f}s before sending next number ({next_number})...")
            await asyncio.sleep(wait_time)

        try:
            latest_messages = [msg async for msg in message.channel.history(limit=1)]
            if latest_messages:
                last_msg = latest_messages[0]
                if last_msg.content.strip().isdigit():
                    latest_digit = int(last_msg.content.strip())
                    if latest_digit >= next_number and last_msg.author.id != bot.user.id:
                        next_number = latest_digit + 1
                    elif last_msg.author.id == bot.user.id:
                        return

            await message.channel.send(str(next_number))
            bot.last_sent_timestamp = time.time()
            print(f"[Success] Sent number: {next_number}")
        except discord.DiscordException as err:
            print(f"[Error] Failed to send message: {err}")

@bot.event
async def on_ready():
    print("=" * 60)
    print(f"Bot Logged in as: {bot.user.name} ({bot.user.id})")
    print(f"Target Channel: {TARGET_CHANNEL_ID}")
    print(f"Slowmode Delay: {SLOWMODE_SECONDS}s")
    print("Ready! Slash commands (/activedev, /badgestatus) are live.")
    print("=" * 60)

# =====================================================================
# LIGHTWEIGHT WEB SERVER (For Render Web Service 24/7 Hosting)
# =====================================================================
async def handle_health_check(request):
    last_exec = bot.badge_state.get("last_executed_at", 0)
    days_elapsed = (time.time() - last_exec) / 86400 if last_exec > 0 else 0
    return web.json_response({
        "status": "healthy",
        "service": "Discord Active Developer Badge Bot",
        "bot_online": bot.is_ready(),
        "bot_user": str(bot.user) if bot.user else None,
        "days_since_last_activedev": round(days_elapsed, 2),
        "target_channel_id": TARGET_CHANNEL_ID
    })

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/healthz", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[Web Server] Render health check HTTP server listening on port {PORT}")

# =====================================================================
# MAIN ENTRYPOINT
# =====================================================================
async def main():
    if not TOKEN or TOKEN.startswith("YOUR_"):
        print("ERROR: DISCORD_BOT_TOKEN is missing or not configured in .env!")
        return

    # Start HTTP web server in background
    await start_web_server()

    # Start Discord Bot
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot process stopped.")
