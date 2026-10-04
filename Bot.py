from flask import Flask
from threading import Thread
import os
import json
import base64
import urllib.request
import urllib.error

app = Flask('')

@app.route('/')
def home():
    return "Bot is active 24/7!"

def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

import discord
from discord.ext import commands
import matplotlib.pyplot as plt
import datetime

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- GITHUB KALIICI VERİTABANI SİSTEMİ ---
DB_FILE = "veritabani.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # Örn: "kullaniciadi/reponame"

def github_veri_cek():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DB_FILE}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    })
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            file_content = base64.b64decode(res_data["content"]).decode("utf-8")
            return json.loads(file_content), res_data["sha"]
    except Exception as e:
        print(f"GitHub'dan veri çekilemedi (İlk çalışmada normal olabilir): {e}")
        return None, None

def github_veri_kaydet(json_string):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DB_FILE}"
    
    # Mevcut dosyanın SHA değerini almalıyız
    _, sha = github_veri_cek()
    
    encoded_content = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")
    payload = {
        "message": "Auto-save database backup [skip ci]",
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha
        
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }, method="PUT")
    
    try:
        with urllib.request.urlopen(req) as response:
            print("Veriler başarıyla GitHub deposuna yedeklendi!")
    except Exception as e:
        print(f"GitHub'a veri kaydedilirken hata oluştu: {e}")

def verileri_yukle():
    # Önce GitHub'dan çekmeyi dene
    gh_data, _ = github_veri_cek()
    if gh_data:
        data = gh_data
    elif os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}

    try:
        loaded_users = {}
        for k, v in data.get("users", {}).items():
            loaded_users[int(k)] = v
            if loaded_users[int(k)].get("last_sell"):
                loaded_users[int(k)]["last_sell"] = datetime.datetime.fromisoformat(loaded_users[int(k)]["last_sell"])
        
        loaded_requests = {}
        for k, v in data.get("pending_requests", {}).items():
            loaded_requests[int(k)] = v

        return loaded_users, data.get("coins", {}), loaded_requests, data.get("request_counter", 1)
    except Exception as e:
        print(f"Veri işlenirken hata: {e}")

    default_users = {}
    default_coins = {
        "ANC": {
            "name": "Anomic Coin",
            "vault_cash": 100000,
            "total_coin": 1000,
            "history": [100.0]
        }
    }
    return default_users, default_coins, {}, 1

def verileri_kaydet():
    users_serializable = {}
    for uid, udata in users.items():
        u_copy = udata.copy()
        if u_copy.get("last_sell"):
            u_copy["last_sell"] = u_copy["last_sell"].isoformat()
        users_serializable[str(uid)] = u_copy

    data = {
        "users": users_serializable,
        "coins": coins,
        "pending_requests": {str(k): v for k, v in pending_requests.items()},
        "request_counter": request_counter
    }
    
    json_str = json.dumps(data, ensure_ascii=False, indent=4)
    
    # Yerel diske yaz
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            f.write(json_str)
    except Exception as e:
        print(f"Yerel kayıt hatası: {e}")
        
    # GitHub'a otomatik commit at
    github_veri_kaydet(json_str)

# Verileri yükle
users, coins, pending_requests, request_counter = verileri_yukle()

def current_price(symbol):
    c = coins[symbol]
    base = c["vault_cash"] / max(c["total_coin"], 1)
    return round(base, 2)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')

# --- PLAYER COMMANDS ---

@bot.command(aliases=['bal'])
async def balance(ctx):
    """Shows full balance and portfolio."""
    uid = ctx.author.id
    if uid not in users:
        users[uid] = {"cash": 0, "coins": {}, "last_sell": None}
    
    u = users[uid]
    message = f"👛 **{ctx.author.name}'s Portfolio:**\n"
    message += f"💵 **Anomic Cash:** `${u['cash']}`\n\n"
    message += "🪙 **Owned Coins:**\n"
    
    if not u["coins"]:
        message += "_No coins owned._\n"
    else:
        for sym, amount in u["coins"].items():
            if amount > 0 and sym in coins:
                price = current_price(sym)
                total_val = round(price * amount, 2)
                message += f"- **{sym}** ({coins[sym]['name']}): `{amount}` units (Value: `${total_val}`)\n"
    
    await ctx.send(message)

@bot.command()
async def market(ctx):
    """Lists all coins and their current prices."""
    if not coins:
        await ctx.send("❌ The market is currently empty.")
        return
        
    msg = "📈 **Anomic Coin Market (Live Prices):**\n"
    for sym, data in coins.items():
        price = current_price(sym)
        msg += f"- **{sym}** ({data['name']}): `${price}`\n"
        
    await ctx.send(msg)

@bot.command()
async def deposit(ctx, amount: int):
    """Opens a cash deposit request (Requires admin approval)."""
    global request_counter
    if amount <= 0:
        await ctx.send("❌ Invalid amount!")
        return
        
    pending_requests[request_counter] = {
        "user_id": ctx.author.id,
        "user_name": ctx.author.name,
        "type": "deposit",
        "amount": amount
    }
    request_counter += 1
    verileri_kaydet()
    await ctx.send(f"📥 **Request #{request_counter - 1} Created:** `${amount}` Anomic Cash deposit request sent to admins.")

@bot.command()
async def withdraw(ctx, amount: int):
    """Opens a cash withdrawal request (Requires admin approval)."""
    global request_counter
    uid = ctx.author.id
    if uid not in users or users[uid]["cash"] < amount:
        await ctx.send("❌ Insufficient Anomic Cash balance!")
        return
        
    pending_requests[request_counter] = {
        "user_id": uid,
        "user_name": ctx.author.name,
        "type": "withdraw",
        "amount": amount
    }
    request_counter += 1
    verileri_kaydet()
    await ctx.send(f"📤 **Request #{request_counter - 1} Created:** `${amount}` Anomic Cash withdrawal request sent to admins.")

@bot.command()
async def buy(ctx, symbol: str, amount: int):
    """Buys specified amount of coins."""
    symbol = symbol.upper()
    if symbol not in coins:
        await ctx.send("❌ Coin not found!")
        return
    if amount <= 0:
        await ctx.send("❌ Amount must be greater than 0!")
        return
        
    uid = ctx.author.id
    if uid not in users:
        users[uid] = {"cash": 0, "coins": {}, "last_sell": None}
        
    price = current_price(symbol)
    cost = int(price * amount)
    
    if users[uid]["cash"] < cost:
        await ctx.send(f"❌ Insufficient balance! Needed: `${cost}`, You have: `${users[uid]['cash']}`")
        return
        
    # Transaction
    users[uid]["cash"] -= cost
    users[uid]["coins"][symbol] = users[uid]["coins"].get(symbol, 0) + amount
    
    # Market update
    coins[symbol]["vault_cash"] += cost
    coins[symbol]["total_coin"] += amount
    new_price = current_price(symbol)
    coins[symbol]["history"].append(new_price)
    
    verileri_kaydet()
    await ctx.send(f"✅ Bought `{amount}` **{symbol}**! Spent: `${cost}`. New Price: `${new_price}`")

@bot.command()
async def sell(ctx, symbol: str, amount: int):
    """Sells coins (80% limit and 24h cooldown included)."""
    symbol = symbol.upper()
    if symbol not in coins:
        await ctx.send("❌ Coin not found!")
        return
        
    uid = ctx.author.id
    if uid not in users or users[uid]["coins"].get(symbol, 0) < amount:
        await ctx.send("❌ Not enough coins!")
        return
        
    current_coins = users[uid]["coins"][symbol]
    max_sellable = int(current_coins * 0.8)
    
    if amount > max_sellable and current_coins > 1:
        await ctx.send(f"⚠️ **80% Sell Limit!** You can sell a maximum of `{max_sellable}` units at once.")
        return
        
    # 24 Hour Cooldown
    now = datetime.datetime.now()
    last = users[uid].get("last_sell")
    if last and (now - last).total_seconds() < 86400:
        rem_sec = 86400 - (now - last).total_seconds()
        hours = int(rem_sec // 3600)
        await ctx.send(f"⏳ You have already sold today! You must wait `{hours}` hours to sell again.")
        return

    price = current_price(symbol)
    profit = int(price * amount * 0.95) # 5% market fee
    
    users[uid]["coins"][symbol] -= amount
    users[uid]["cash"] += profit
    users[uid]["last_sell"] = now
    
    # Market update
    coins[symbol]["vault_cash"] = max(1000, coins[symbol]["vault_cash"] - profit)
    coins[symbol]["total_coin"] = max(10, coins[symbol]["total_coin"] - amount)
    new_price = current_price(symbol)
    coins[symbol]["history"].append(new_price)
    
    verileri_kaydet()
    await ctx.send(f"📉 Sold `{amount}` **{symbol}** (5% fee deducted). Earned: `${profit}`. New Price: `${new_price}`")

@bot.command()
async def chart(ctx, symbol: str = "ANC"):
    """Generates a chart image for the selected coin."""
    symbol = symbol.upper()
    if symbol not in coins:
        await ctx.send("❌ Coin not found!")
        return
        
    plt.figure(figsize=(8, 4))
    plt.plot(coins[symbol]["history"], marker='o', color='gold', linewidth=2)
    plt.title(f'{coins[symbol]["name"]} ({symbol}) Live Chart')
    plt.xlabel('Transactions')
    plt.ylabel('Price ($)')
    plt.grid(True)
    
    file_name = f"{symbol}_chart.png"
    plt.savefig(file_name)
    plt.close()
    
    await ctx.send(file=discord.File(file_name))

# --- ADMIN COMMANDS ---

@bot.command()
@commands.has_permissions(administrator=True)
async def requests(ctx):
    """Lists pending deposit and withdrawal requests."""
    if not pending_requests:
        await ctx.send("👌 No pending requests.")
        return
        
    msg = "📋 **Pending Money Requests:**\n"
    for tid, t in pending_requests.items():
        msg += f"- **ID #{tid}:** {t['user_name']} | Type: `{t['type'].upper()}` | Amount: `${t['amount']}`\n"
    msg += "\nTo approve: `!approve [ID]` | To deny: `!deny [ID]`"
    await ctx.send(msg)

@bot.command()
@commands.has_permissions(administrator=True)
async def approve(ctx, req_id: int):
    """Approves a money request."""
    if req_id not in pending_requests:
        await ctx.send("❌ Invalid Request ID!")
        return
        
    t = pending_requests.pop(req_id)
    uid = t["user_id"]
    if uid not in users:
        users[uid] = {"cash": 0, "coins": {}, "last_sell": None}
        
    if t["type"] == "deposit":
        users[uid]["cash"] += t["amount"]
        await ctx.send(f"✅ Deposit ID #{req_id} approved! `${t['amount']}` added to <@{uid}>.")
    elif t["type"] == "withdraw":
        users[uid]["cash"] -= t["amount"]
        await ctx.send(f"✅ Withdrawal ID #{req_id} approved! `${t['amount']}` deducted from <@{uid}>. You can deliver it in-game.")
    
    verileri_kaydet()

@bot.command()
@commands.has_permissions(administrator=True)
async def deny(ctx, req_id: int):
    """Denies a money request."""
    if req_id not in pending_requests:
        await ctx.send("❌ Invalid Request ID!")
        return
    pending_requests.pop(req_id)
    verileri_kaydet()
    await ctx.send(f"🚫 Request #{req_id} denied.")

@bot.command()
@commands.has_permissions(administrator=True)
async def createcoin(ctx, symbol: str, name: str, init_vault: int, init_coin: int):
    """Creates a new coin type."""
    symbol = symbol.upper()
    if symbol in coins:
        await ctx.send("❌ A coin with this symbol already exists!")
        return
        
    coins[symbol] = {
        "name": name,
        "vault_cash": init_vault,
        "total_coin": init_coin,
        "history": [round(init_vault / init_coin, 2)]
    }
    verileri_kaydet()
    await ctx.send(f"🎉 **New Coin Created:** {name} ({symbol}) - Starting Price: `${current_price(symbol)}`")

@bot.command()
@commands.has_permissions(administrator=True)
async def deletecoin(ctx, symbol: str):
    """Completely removes a coin type from the market."""
    symbol = symbol.upper()
    if symbol not in coins:
        await ctx.send("❌ Coin not found!")
        return
        
    del coins[symbol]
    verileri_kaydet()
    await ctx.send(f"🗑️ **{symbol}** has been completely removed from the market.")

@bot.command()
@commands.has_permissions(administrator=True)
async def manipulate(ctx, symbol: str, multiplier: float):
    """Manipulates price by changing the vault cash with a multiplier."""
    symbol = symbol.upper()
    if symbol not in coins:
        await ctx.send("❌ Coin not found!")
        return
        
    coins[symbol]["vault_cash"] = int(coins[symbol]["vault_cash"] * multiplier)
    new_price = current_price(symbol)
    coins[symbol]["history"].append(new_price)
    verileri_kaydet()
    await ctx.send(f"⚡ **Market Manipulation!** {symbol} vault updated. New Price: `${new_price}`")

bot.run(os.getenv("TOKEN"))
