# Discord Active Developer Badge & 24/7 Counting Bot

Automated Discord bot designed for 24/7 hosting on Render with an embedded HTTP health-check server and automatic 29-day badge expiration alerts.

## Features
- **Active Developer Badge Slash Command (`/activedev`)**: Owner/Server Owner restricted application command to qualify for and renew the Discord Active Developer Badge.
- **Badge Status Command (`/badgestatus`)**: Displays remaining days/hours until the 30-day deadline and the next warning date.
- **Automated 29-Day Expiration Alert**: Pings the bot owner in the target channel 24 hours before the 30-day window expires.
- **Built-in Render Health Check Server**: Runs an internal `aiohttp` web server on `$PORT` to satisfy Render Web Service 24/7 uptime requirements.
- **Automated Counting Bot**: Automatically counts numbers in the target channel with configurable slowmode cooldown.

## Deployment on Render
1. Create a new **Web Service** on [Render](https://dashboard.render.com).
2. Connect this GitHub repository.
3. Configure settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python counting_bot.py`
4. Add Environment Variables:
   - `DISCORD_BOT_TOKEN`: Your Discord Bot Token
   - `BOT_OWNER_ID`: Your Discord User ID
   - `TARGET_CHANNEL_ID`: Channel ID for alerts and counting
   - `SLOWMODE_SECONDS`: Cooldown in seconds (e.g., 30)
