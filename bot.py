import logging, random, asyncio, os
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------
# In-Memory Database
# -------------------
players = {}
auctions = {}
alliances = {}
events = []

# -------------------
# Constants
# -------------------
BUSINESSES = {
    'lemonade_stand': {'name':'🍋 Lemonade Stand','base_cost':100,'base_income':1,'multiplier':1.15},
    'coffee_shop': {'name':'☕ Coffee Shop','base_cost':1000,'base_income':10,'multiplier':1.15},
    'restaurant': {'name':'🍔 Restaurant','base_cost':10000,'base_income':100,'multiplier':1.15},
    'factory': {'name':'🏭 Factory','base_cost':100000,'base_income':1000,'multiplier':1.15},
    'tech_startup': {'name':'💻 Tech Startup','base_cost':1000000,'base_income':10000,'multiplier':1.15},
    'bank': {'name':'🏦 Bank','base_cost':10000000,'base_income':100000,'multiplier':1.15},
    'oil_empire': {'name':'🛢️ Oil Empire','base_cost':100000000,'base_income':1000000,'multiplier':1.15},
    'space_corp': {'name':'🚀 Space Corp','base_cost':1000000000,'base_income':10000000,'multiplier':1.15},
}

UPGRADES = {
    'multi_x2': {'name':'📈 Income x2','cost':5000,'effect':2},
    'multi_x5': {'name':'📈 Income x5','cost':50000,'effect':5},
    'multi_x10': {'name':'📈 Income x10','cost':500000,'effect':10},
}

DAILY_REWARD = 5000
LOOTBOX_ITEMS = ['💎 Diamond', '🖤 Dark Matter', '🏆 Trophy', '🛡️ Shield', '⚡ Lightning']

# -------------------
# Utility Functions
# -------------------
def format_number(num):
    if num>=1e12: return f"${num/1e12:.2f}T"
    if num>=1e9: return f"${num/1e9:.2f}B"
    if num>=1e6: return f"${num/1e6:.2f}M"
    if num>=1e3: return f"${num/1e3:.2f}K"
    return f"${num:.2f}"

def get_player(user_id):
    if user_id not in players:
        players[user_id] = {
            'username':'Unknown',
            'money':1000,
            'businesses':defaultdict(int),
            'income_multiplier':1,
            'upgrades':[],
            'prestige_level':0,
            'prestige_bonus':1,
            'total_earned':0,
            'raids_won':0,
            'raids_lost':0,
            'notoriety':0,
            'rare_items':[],
            'achievements':[],
            'last_collect':datetime.now(),
            'last_daily':datetime.now()-timedelta(days=1)
        }
    return players[user_id]

def calculate_income(player):
    total=0
    for biz_id,count in player['businesses'].items():
        total += BUSINESSES[biz_id]['base_income']*count
    total *= player['income_multiplier']*player['prestige_bonus']
    player['income_per_sec'] = total
    return total

def collect_idle_income(player):
    now = datetime.now()
    delta = (now - player['last_collect']).total_seconds()
    delta = min(delta, 14400)
    income = player.get('income_per_sec',0)*delta
    player['money'] += income
    player['total_earned'] += income
    player['last_collect'] = now
    return income, delta

# -------------------
# Commands
# -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    player['username'] = user.username or user.first_name
    collect_idle_income(player)
    await update.message.reply_text(f"🔥 Welcome {player['username']} to Empire Wars! 🔥\nUse /empire to view your empire.\nUse /help for commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = """
🔥 **Empire Wars Commands** 🔥
/empire - View your empire 🏰
/collect - Collect idle income 💰
/profile - Your detailed stats 👤
/leaderboard - Top players 🏆
/daily - Claim daily rewards 🎁
/raid @username - Attack a player ⚔️
/flex - Show your empire, badges & rare items 💎
/create_alliance <name> - Form alliance 👥
/join_alliance <name> - Join alliance 🤝
/leave_alliance - Leave alliance ❌
/alliance_info - View alliance stats 📊
/auction - View active auctions 🏪
/bid <item#> <amount> - Place a bid 💸
/lottery - Try your luck 🎲
/challenge @username - 1v1 mini-game 🔥
/blackmarket - Rare secret items 🕵️‍♂️
"""
    await update.message.reply_text(commands)

async def empire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    collect_idle_income(player)
    calculate_income(player)
    text = f"🏰 Empire of {player['username']}:\nMoney: {format_number(player['money'])}\nIncome: {format_number(player['income_per_sec'])}/sec\nPrestige: {player['prestige_level']} ({player['prestige_bonus']}x)"
    await update.message.reply_text(text)

async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    income, _ = collect_idle_income(player)
    await update.message.reply_text(f"💰 Collected {format_number(income)}!")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    calculate_income(player)
    text = f"👤 Profile: {player['username']}\nMoney: {format_number(player['money'])}\nIncome: {format_number(player['income_per_sec'])}/sec\nPrestige: {player['prestige_level']}\nRare Items: {', '.join(player['rare_items']) if player['rare_items'] else 'None'}\nAchievements: {', '.join(player['achievements']) if player['achievements'] else 'None'}"
    await update.message.reply_text(text)

# -------------------
# Placeholder handlers for GC/interactive features
# -------------------
async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚔️ Raid feature coming soon!")

async def auction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏪 Auction feature coming soon!")

async def create_alliance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 Alliance creation coming soon!")

# -------------------
# Main
# -------------------
def main():
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN: print("❌ Set BOT_TOKEN!"); return
    app = Application.builder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("empire", empire))
    app.add_handler(CommandHandler("collect", collect))
    app.add_handler(CommandHandler("profile", profile))
    
    print("🔥 Empire Wars Bot Fully Loaded! 🔥")
    app.run_polling()

if __name__=="__main__":
    main()
