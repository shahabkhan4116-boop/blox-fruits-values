import discord
import aiohttp
import os
from discord.ext import tasks
from bs4 import BeautifulSoup

# ========== YOUR SETTINGS ==========
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
VALUE_CHANNEL_NAME = "『🤔』trading-values"
# ====================================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

tracked_messages = {}
cached_values = {}

async def fetch_all_values():
    url = "https://bloxfruitstradehub.com/values"
    headers = {"User-Agent": "Mozilla/5.0"}
    fruits = {}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                return {}
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue
            try:
                name_tag = cols[0].find("a")
                name = name_tag.text.strip() if name_tag else cols[0].text.strip()
                href = name_tag["href"] if name_tag else ""
                item_url = "https://bloxfruitstradehub.com" + href
                rarity = cols[1].text.strip()
                value = cols[2].text.strip() or "N/A"
                perm_value = cols[3].text.strip() or "N/A"
                demand = cols[4].text.strip() or "N/A"
                trend = cols[5].text.strip() if len(cols) > 5 else "N/A"

                key = name.lower().replace(" ", "-")
                fruits[key] = {
                    "name": name,
                    "rarity": rarity,
                    "value": value,
                    "perm_value": perm_value,
                    "demand": demand,
                    "trend": trend,
                    "url": item_url,
                }
            except:
                continue

    return fruits

def find_fruit(query, fruits):
    query_key = query.lower().strip().replace(" ", "-")
    if query_key in fruits:
        return fruits[query_key]
    for key, data in fruits.items():
        if query_key == key:
            return data
    query_words = set(query_key.split("-"))
    for key, data in fruits.items():
        key_words = set(key.split("-"))
        if query_words == key_words:
            return data
    for key, data in fruits.items():
        if query_key in key:
            return data
    return None

def get_color(rarity):
    colors = {
        "Mythical": discord.Color.red(),
        "Legendary": discord.Color.orange(),
        "Rare": discord.Color.blue(),
        "Uncommon": discord.Color.green(),
        "Common": discord.Color.light_grey(),
        "Limited": discord.Color.gold(),
        "Gamepass": discord.Color.purple()
    }
    return colors.get(rarity, discord.Color.blurple())

def get_rarity_emoji(rarity):
    emojis = {
        "Mythical": "🔴",
        "Legendary": "🟠",
        "Rare": "🔵",
        "Uncommon": "🟢",
        "Common": "⚪",
        "Limited": "⭐",
        "Gamepass": "💎"
    }
    return emojis.get(rarity, "❓")

def build_embed(data, permanent):
    value_display = data["perm_value"] if permanent else data["value"]
    if value_display == "—" or not value_display:
        value_display = "N/A"

    rarity_emoji = get_rarity_emoji(data["rarity"])
    if permanent:
        title = f"🔮 Permanent {data['name']}"
    else:
        title = f"🍎 {data['name']}"

    embed = discord.Embed(
        title=title,
        url=data["url"],
        color=get_color(data["rarity"])
    )

    embed.add_field(name="💰 Value", value=f"**{value_display}**", inline=False)
    embed.add_field(name="📊 Demand", value=f"**{data['demand']}**", inline=True)
    embed.add_field(name="📈 Trend", value=f"**{data['trend']}**", inline=True)
    embed.add_field(name=f"{rarity_emoji} Rarity", value=f"**{data['rarity']}**", inline=True)
    embed.set_footer(text="bloxfruitstradehub.com • Updates every 6 hours")
    return embed

@tasks.loop(hours=6)
async def update_tracked_messages():
    global cached_values
    if not tracked_messages:
        return
    cached_values = await fetch_all_values()
    for fruit_key, info in list(tracked_messages.items()):
        try:
            data = find_fruit(fruit_key, cached_values)
            if data:
                new_embed = build_embed(data, info["permanent"])
                await info["message"].edit(embed=new_embed)
        except Exception as e:
            print(f"Failed to update {fruit_key}: {e}")

@client.event
async def on_ready():
    global cached_values
    print(f"Bot is online as {client.user}")
    cached_values = await fetch_all_values()
    print(f"Loaded {len(cached_values)} items!")
    update_tracked_messages.start()

@client.event
async def on_message(message):
    global cached_values
    if message.author.bot:
        return
    if message.channel.name != VALUE_CHANNEL_NAME:
        return

    content = message.content.lower().strip()

    if not content.startswith("what is") or "value" not in content:
        return

    permanent = "permanent" in content

    try:
        fruit_part = content.replace("what is", "").strip()
        fruit_part = fruit_part.replace("permanent", "").strip()
        fruit_name = fruit_part.replace("'s value?", "").replace("'s value", "").strip()
    except:
        return

    if not fruit_name:
        return

    async with message.channel.typing():
        data = find_fruit(fruit_name, cached_values)

    if not data:
        await message.channel.send(
            embed=discord.Embed(
                title="❌ Not Found",
                description=f"Could not find **{fruit_name.title()}**.\nMake sure the name is spelled correctly!",
                color=discord.Color.red()
            )
        )
        return

    embed = build_embed(data, permanent)
    sent = await message.channel.send(embed=embed)

    fruit_key = data["name"].lower().replace(" ", "-")
    tracked_messages[fruit_key] = {
        "message": sent,
        "permanent": permanent
    }

client.run(DISCORD_TOKEN)
