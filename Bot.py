from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot 7/24 Aktif!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()import discord
from discord.ext import commands, tasks
import matplotlib.pyplot as plt
import datetime
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- VERİ YAPISI ---
# Kullanıcılar: {user_id: {"cash": 5000, "coins": {"ANC": 10}, "last_sell": datetime}}
kullanicilar = {}

# Coinler: {symbol: {"name": "Anomic Coin", "kasa_nakit": 100000, "toplam_coin": 1000, "history": [100.0]}}
coinler = {
    "ANC": {
        "name": "Anomic Coin",
        "kasa_nakit": 100000,
        "toplam_coin": 1000,
        "history": [100.0]
    }
}

bekleyen_talepler = {} # {talep_id: {"user_id": ..., "tip": "deposit/take", "miktar": ...}}
talep_sayac = 1

def guncel_fiyat(symbol):
    c = coinler[symbol]
    base = c["kasa_nakit"] / max(c["toplam_coin"], 1)
    return round(base, 2)

@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yapıldı!')

# --- OYUNCU KOMUTLARI ---

@bot.command()
async def bal(ctx):
    """Tüm bakiye ve portföyü gösterir."""
    uid = ctx.author.id
    if uid not in kullanicilar:
        kullanicilar[uid] = {"cash": 0, "coins": {}, "last_sell": None}
    
    u = kullanicilar[uid]
    mesaj = f"👛 **{ctx.author.name} Portföyü:**\n"
    mesaj += f"💵 **Anomic Cash:** `${u['cash']}`\n\n"
    mesaj += "🪙 **Sahip Olunan Coin'ler:**\n"
    
    if not u["coins"]:
        mesaj += "_Hiç coin yok._\n"
    else:
        for sym, miktar in u["coins"].items():
            if miktar > 0 and sym in coinler:
                fiyat = guncel_fiyat(sym)
                toplam_val = round(fiyat * miktar, 2)
                mesaj += f"- **{sym}** ({coinler[sym]['name']}): `{miktar}` adet (Değeri: `${toplam_val}`)\n"
    
    await ctx.send(mesaj)

@bot.command()
async def deposit(ctx, miktar: int):
    """Nakit yükleme talebi açar (Moderatör onayı gerektirir)."""
    global talep_sayac
    if miktar <= 0:
        await ctx.send("❌ Geçersiz miktar!")
        return
        
    bekleyen_talepler[talep_sayac] = {
        "user_id": ctx.author.id,
        "user_name": ctx.author.name,
        "tip": "deposit",
        "miktar": miktar
    }
    await ctx.send(f"📥 **Talep #{talep_sayac} Oluşturuldu:** `${miktar}` Anomic Cash yatırma talebiniz yetkililere iletildi.")
    talep_sayac += 1

@bot.command()
async def take(ctx, miktar: int):
    """Nakit çekme talebi açar (Moderatör onayı gerektirir)."""
    global talep_sayac
    uid = ctx.author.id
    if uid not in kullanicilar or kullanicilar[uid]["cash"] < miktar:
        await ctx.send("❌ Yetersiz Anomic Cash bakiyesi!")
        return
        
    bekleyen_talepler[talep_sayac] = {
        "user_id": uid,
        "user_name": ctx.author.name,
        "tip": "take",
        "miktar": miktar
    }
    await ctx.send(f"📤 **Talep #{talep_sayac} Oluşturuldu:** `${miktar}` Anomic Cash çekme talebiniz yetkililere iletildi.")
    talep_sayac += 1

@bot.command()
async def al(ctx, symbol: str, miktar: int):
    """Coin satın alma."""
    symbol = symbol.upper()
    if symbol not in coinler:
        await ctx.send("❌ Böyle bir coin bulunamadı!")
        return
    if miktar <= 0:
        await ctx.send("❌ Miktar 0'dan büyük olmalı!")
        return
        
    uid = ctx.author.id
    if uid not in kullanicilar:
        kullanicilar[uid] = {"cash": 0, "coins": {}, "last_sell": None}
        
    fiyat = guncel_fiyat(symbol)
    maliyet = int(fiyat * miktar)
    
    if kullanicilar[uid]["cash"] < maliyet:
        await ctx.send(f"❌ Yetersiz bakiye! Gereken: `${maliyet}`, Sende olan: `${kullanicilar[uid]['cash']}`")
        return
        
    # İşlem
    kullanicilar[uid]["cash"] -= maliyet
    kullanicilar[uid]["coins"][symbol] = kullanicilar[uid]["coins"].get(symbol, 0) + miktar
    
    # Borsa güncellemesi
    coinler[symbol]["kasa_nakit"] += maliyet
    coinler[symbol]["toplam_coin"] += miktar
    yeni_f = guncel_fiyat(symbol)
    coinler[symbol]["history"].append(yeni_f)
    
    await ctx.send(f"✅ `{miktar}` adet **{symbol}** alındı! Harcanan: `${maliyet}`. Yeni Fiyat: `${yeni_f}`")

@bot.command()
async def sat(ctx, symbol: str, miktar: int):
    """Coin satma (%80 limiti ve 24 saatlik kota içerir)."""
    symbol = symbol.upper()
    if symbol not in coinler:
        await ctx.send("❌ Böyle bir coin bulunamadı!")
        return
        
    uid = ctx.author.id
    if uid not in kullanicilar or kullanicilar[uid]["coins"].get(symbol, 0) < miktar:
        await ctx.send("❌ Yeterli coin'in yok!")
        return
        
    mevcut_coin = kullanicilar[uid]["coins"][symbol]
    max_satilabilir = int(mevcut_coin * 0.8) # Tek seferde en fazla %80
    
    if miktar > max_satilabilir and mevcut_coin > 1:
        await ctx.send(f"⚠️ **%80 Satış Limiti!** Tek seferde en fazla `{max_satilabilir}` adet satabilirsin (`all` satışı engellenmiştir).")
        return
        
    # 24 Saatlik Soğuma Kontrolü
    now = datetime.datetime.now()
    last = kullanicilar[uid].get("last_sell")
    if last and (now - last).total_seconds() < 86400:
        kalan_sn = 86400 - (now - last).total_seconds()
        saat = int(kalan_sn // 3600)
        await ctx.send(f"⏳ Bugün zaten satış yaptın! Yeniden satış yapmak için `{saat}` saat beklemelisin.")
        return

    fiyat = guncel_fiyat(symbol)
    kazanc = int(fiyat * miktar * 0.95) # %5 borsa komisyonu kesintisi
    
    kullanicilar[uid]["coins"][symbol] -= miktar
    kullanicilar[uid]["cash"] += kazanc
    kullanicilar[uid]["last_sell"] = now
    
    # Borsa güncellemesi
    coinler[symbol]["kasa_nakit"] = max(1000, coinler[symbol]["kasa_nakit"] - kazanc)
    coinler[symbol]["toplam_coin"] = max(10, coinler[symbol]["toplam_coin"] - miktar)
    yeni_f = guncel_fiyat(symbol)
    coinler[symbol]["history"].append(yeni_f)
    
    await ctx.send(f"📉 `{miktar}` adet **{symbol}** satıldı (%5 komisyon düşüldü). Kazanılan: `${kazanc}`. Yeni Fiyat: `${yeni_f}`")

@bot.command()
async def grafik(ctx, symbol: str = "ANC"):
    """Seçilen coin'in grafik görselini üretir."""
    symbol = symbol.upper()
    if symbol not in coinler:
        await ctx.send("❌ Coin bulunamadı!")
        return
        
    plt.figure(figsize=(8, 4))
    plt.plot(coinler[symbol]["history"], marker='o', color='gold', linewidth=2)
    plt.title(f'{coinler[symbol]["name"]} ({symbol}) Canlı Grafik')
    plt.xlabel('İşlem Adımları')
    plt.ylabel('Fiyat ($)')
    plt.grid(True)
    
    dosya_adi = f"{symbol}_grafik.png"
    plt.savefig(dosya_adi)
    plt.close()
    
    await ctx.send(file=discord.File(dosya_adi))

# --- MODERATÖR / ADMIN KOMUTLARI ---

@bot.command()
@commands.has_permissions(administrator=True)
async def talepler(ctx):
    """Bekleyen deposit ve take taleplerini listeler."""
    if not bekleyen_talepler:
        await ctx.send("👌 Bekleyen talep yok.")
        return
        
    msg = "📋 **Bekleyen Para Talepleri:**\n"
    for tid, t in bekleyen_talepler.items():
        msg += f"- **ID #{tid}:** {t['user_name']} | Tür: `{t['tip'].upper()}` | Miktar: `${t['miktar']}`\n"
    msg += "\nOnaylamak için: `!onayla [ID]` | Reddetmek için: `!reddet [ID]`"
    await ctx.send(msg)

@bot.command()
@commands.has_permissions(administrator=True)
async def onayla(ctx, talep_id: int):
    """Para talebini onaylar."""
    if talep_id not in bekleyen_talepler:
        await ctx.send("❌ Geçersiz Talep ID!")
        return
        
    t = bekleyen_talepler.pop(talep_id)
    uid = t["user_id"]
    if uid not in kullanicilar:
        kullanicilar[uid] = {"cash": 0, "coins": {}, "last_sell": None}
        
    if t["tip"] == "deposit":
        kullanicilar[uid]["cash"] += t["miktar"]
        await ctx.send(f"✅ #{talep_id} ID'li deposit onaylandı! <@{uid}> hesabına `${t['miktar']}` eklendi.")
    elif t["tip"] == "take":
        kullanicilar[uid]["cash"] -= t["miktar"]
        await ctx.send(f"✅ #{talep_id} ID'li take onaylandı! <@{uid}> hesabından `${t['miktar']}` düşüldü. Oyunda teslim edebilirsiniz.")

@bot.command()
@commands.has_permissions(administrator=True)
async def reddet(ctx, talep_id: int):
    """Para talebini reddeder."""
    if talep_id not in bekleyen_talepler:
        await ctx.send("❌ Geçersiz Talep ID!")
        return
    bekleyen_talepler.pop(talep_id)
    await ctx.send(f"🚫 #{talep_id} ID'li talep reddedildi.")

@bot.command()
@commands.has_permissions(administrator=True)
async def coinolustur(ctx, symbol: str, isim: str, baslangic_kasa: int, baslangic_coin: int):
    """Yeni bir coin türü tanımlar."""
    symbol = symbol.upper()
    if symbol in coinler:
        await ctx.send("❌ Bu sembolle zaten bir coin var!")
        return
        
    coinler[symbol] = {
        "name": isim,
        "kasa_nakit": baslangic_kasa,
        "toplam_coin": baslangic_coin,
        "history": [round(baslangic_kasa / baslangic_coin, 2)]
    }
    await ctx.send(f"🎉 **Yeni Coin Oluşturuldu:** {isim} ({symbol}) - Başlangıç Fiyatı: `${guncel_fiyat(symbol)}`")

@bot.command()
@commands.has_permissions(administrator=True)
async def mudahele(ctx, symbol: str, carpan: float):
    """Seçilen coinin kasa nakdini çarpanla değiştirerek fiyatı manipüle eder."""
    symbol = symbol.upper()
    if symbol not in coinler:
        await ctx.send("❌ Coin bulunamadı!")
        return
        
    coinler[symbol]["kasa_nakit"] = int(coinler[symbol]["kasa_nakit"] * carpan)
    yeni_f = guncel_fiyat(symbol)
    coinler[symbol]["history"].append(yeni_f)
    await ctx.send(f"⚡ **Piyasa Müdahalesi!** {symbol} kasası güncellendi. Yeni Fiyat: `${yeni_f}`")

# TOKEN BURAYA YAZILACAK
bot.run(os.getenv("TOKEN"))
