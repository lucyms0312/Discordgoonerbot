import discord
from discord.ext import commands
import aiohttp
import asyncio
import os
from dotenv import load_dotenv
import json
import random

# -------------------- LOAD ENV --------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEV_IDS = [int(x) for x in os.getenv("DEV_IDS", "").split(",") if x]
RULE34_API_KEY = os.getenv("RULE34_API_KEY", "")
RULE34_USER_ID = os.getenv("RULE34_USER_ID")
PREFIX = "?"
MAX_IMAGES = 50  # Max images per request

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"Signed in as {bot.user} (ID: {bot.user.id})")

# -------------------- BLACKLIST --------------------
BLACKLIST = [
    "loli", "shota", "gore", "rape", "scat", "bestiality", "inflation", "cumflation", "self_harm", "shit", "abdl", "strawberry_shortcake", "ugly", "stomach_rumbling", "stomach rumbling", "self harm", "cum-flation",
    "poop", "guy", "masculine", "fat", "chubby", "plus size", "overweight", "lifelike animal", "anthropmorphic"
]

OPTIONAL_BLACKLIST = [
    "pregnant", "pregnancy", "giantess", "tentacles"
]

# -------------------- HELPERS --------------------
async def fetch_json(url, params=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            try:
                return await resp.json(content_type=None)
            except:
                text = await resp.text()
                try:
                    return json.loads(text)
                except:
                    return None

def is_dev():
    async def predicate(ctx):
        return ctx.author.id in DEV_IDS
    return commands.check(predicate)

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")

def get_image_url(post):
    url = post.get("file_url") or post.get("large_file_url")
    if url and url.lower().endswith(VALID_EXTENSIONS) and url.startswith(("http://", "https://")):
        return url
    return None

# -------------------- IMAGE SENDING --------------------
async def send_images(ctx, tags, amount, site):
    # Check blacklist (case-insensitive)
    if any(word.lower() in tags.lower() for word in BLACKLIST):
        await ctx.send("Your search contains forbidden terms.")
        return
    optional_blacklist_enabled = True
    if optional_blacklist_enabled:
        if any(word.lower() in tags.lower() for word in OPTIONAL_BLACKLIST):
            await ctx.send("Your search contains forbidden terms.")
            return

    if site == "rule34":
        tags_for_url = tags.strip()
        api_url = "https://api.rule34.xxx/index.php"
        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": 1,
            "tags": tags_for_url,
            "limit": 100,
            "api_key": RULE34_API_KEY,
            "user_id": RULE34_USER_ID
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params) as resp:
                if resp.status != 200:
                    await ctx.send("No results found.")
                    return
                text = await resp.text()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            text = text.strip()
            if text.startswith("<") or not text:
                await ctx.send(f"No valid results found for `{tags}`.")
                return
            try:
                data = json.loads(text)
            except:
                await ctx.send(f"Rule34 API returned invalid data for `{tags}`.")
                return
    else:
        if site == "danbooru":
            api_url = "https://danbooru.donmai.us/posts.json"
        elif site == "konachan":
            api_url = "https://konachan.com/post.json"
        elif site == "yandere":
            api_url = "https://yande.re/post.json"
        params = {"tags": tags, "limit": 100}
        data = await fetch_json(api_url, params=params)
        if not data:
            await ctx.send(f"No results found for `{tags}`.")
            return

    if isinstance(data, dict):
        data = [data]
    elif isinstance(data, list):
        data = [d for d in data if isinstance(d, dict)]
    else:
        await ctx.send(f"No valid posts found for `{tags}`.")
        return

    sent_count = 0
    tries = 0
    used_ids = set()
    max_tries = 500

    while sent_count < amount and tries < max_tries:
        tries += 1
        available_posts = [p for p in data if isinstance(p, dict) and p.get("id") not in used_ids and get_image_url(p)]
        if not available_posts:
            break
        post = random.choice(available_posts)
        used_ids.add(post.get("id"))
        img_url = get_image_url(post)
        if not img_url:
            continue
        embed = discord.Embed(color=0xFF0000)
        embed.set_image(url=img_url)
        try:
            await ctx.send(embed=embed)
        except discord.HTTPException:
            await ctx.send(f"Failed to send embed for image: {img_url}")
        sent_count += 1
        await asyncio.sleep(1)  # 1-second delay

    if sent_count < amount:
        await ctx.send(f"Only found {sent_count} valid images for `{tags}`.")

# -------------------- CUSTOM COMMANDS --------------------
@bot.command()
async def viewblacklist(ctx):
    if not BLACKLIST:
        await ctx.send("Blacklist is empty.")
        return
    terms = ", ".join(BLACKLIST)
    embed = discord.Embed(
        title="X Blacklisted terms",
        description=f"The following terms are forbidden:\n{terms}",
        color=0xFF0000
    )
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"don't ping me again bitch. speed is {latency_ms}ms")

# -------------------- IMAGE COMMANDS --------------------
@bot.command()
async def danbooru(ctx, *, tags):
    amount = 5
    split_tags = tags.split()
    if split_tags[0].isdigit():
        amount = min(int(split_tags[0]), MAX_IMAGES)
        tags = " ".join(split_tags[1:])
    await send_images(ctx, tags, amount, "danbooru")

@bot.command()
async def konachan(ctx, *, tags):
    amount = 5
    split_tags = tags.split()
    if split_tags[0].isdigit():
        amount = min(int(split_tags[0]), MAX_IMAGES)
        tags = " ".join(split_tags[1:])
    await send_images(ctx, tags, amount, "konachan")

@bot.command()
async def yandere(ctx, *, tags):
    amount = 5
    split_tags = tags.split()
    if split_tags[0].isdigit():
        amount = min(int(split_tags[0]), MAX_IMAGES)
        tags = " ".join(split_tags[1:])
    await send_images(ctx, tags, amount, "yandere")

@bot.command()
async def rule34(ctx, *, tags):
    amount = 5
    split_tags = tags.split()
    if split_tags[0].isdigit():
        amount = min(int(split_tags[0]), MAX_IMAGES)
        tags = " ".join(split_tags[1:])
    if not RULE34_API_KEY or not RULE34_USER_ID:
        await ctx.send("Rule34 API key or user ID is missing. Please set them in your .env file.")
        return
    await send_images(ctx, tags, amount, "rule34")

# -------------------- MODERATION COMMANDS --------------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, user: discord.Member):
    await user.ban()
    await ctx.send(f"Banned {user}")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, user: discord.Member):
    await user.kick()
    await ctx.send(f"Kicked {user}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, user: discord.Member, minutes: int):
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await ctx.guild.create_role(name="Muted")
        for ch in ctx.guild.channels:
            await ch.set_permissions(mute_role, send_messages=False, speak=False)
    await user.add_roles(mute_role)
    await ctx.send(f"Muted {user} for {minutes} minutes")
    await asyncio.sleep(minutes*60)
    await user.remove_roles(mute_role)
    await ctx.send(f"Unmuted {user}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"Purged {len(deleted)} messages.", delete_after=5)

# -------------------- DEV COMMANDS --------------------
@bot.command()
@is_dev()
async def changebotusername(ctx, *, username):
    await bot.user.edit(username=username)
    await ctx.send(f"Username changed to {username}")

@bot.command()
@is_dev()
async def shutdown(ctx):
    await ctx.send("Shutting down...")
    await bot.close()

@bot.command()
@is_dev()
async def setbotstatus(ctx, status_type, *, text):
    status_type = status_type.lower()
    if status_type == "playing":
        activity = discord.Game(text)
    elif status_type == "watching":
        activity = discord.Activity(type=discord.ActivityType.watching, name=text)
    elif status_type == "listening":
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)
    elif status_type == "streaming":
        activity = discord.Streaming(name=text, url="https://twitch.tv/example")
    else:
        await ctx.send("Invalid status type. Choose: playing, watching, listening, streaming")
        return
    await bot.change_presence(activity=activity)
    await ctx.send(f"Bot status updated: {status_type} {text}")

# -------------------- CUSTOM HELP --------------------
@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="Bot Commands Help",
        description=f"Use `{PREFIX}` before each command.\nAll commands below are available:",
        color=0xFF0000
    )

    embed.add_field(name="🎨 Image Commands", value=(
        "`danbooru [amount] <tags>`\n"
        "`yandere [amount] <tags>`\n"
        "`konachan [amount] <tags>`\n"
        "`rule34 [amount] <tags>`\n"
        "(If amount is not specified, defaults to 5)"
    ), inline=False)

    embed.add_field(name="🛡 Moderation Commands", value=(
        "`ban <user>`\n"
        "`kick <user>`\n"
        "`mute <user> <minutes>`\n"
        "`purge <amount>`"
    ), inline=False)

    embed.add_field(name="💻 Developer Commands", value=(
        "`changebotusername <username>`\n"
        "`shutdown`\n"
        "`setbotstatus <playing|watching|listening|streaming> <text>`"
    ), inline=False)

    embed.add_field(name="Helper commands", value=(
        "`viewblacklist`"
    ), inline=False)

    await ctx.send(embed=embed)

# -------------------- RUN BOT --------------------
bot.run(TOKEN)
