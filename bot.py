import logging
import os
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
from threading import Thread

# Flask app for Render health check
app = Flask(__name__)

@app.route('/')
def home():
    return "🔥 Empire Wars Bot is ALIVE! 🔥"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Game data
players = {}
leaderboard_cache = []
last_leaderboard_update = datetime.now()

BUSINESSES = {
    'lemonade_stand': {'name': '🍋 Lemonade Stand', 'base_cost': 100, 'base_income': 1, 'multiplier': 1.15},
    'coffee_shop': {'name': '☕ Coffee Shop', 'base_cost': 1000, 'base_income': 10, 'multiplier': 1.15},
    'restaurant': {'name': '🍔 Restaurant', 'base_cost': 10000, 'base_income': 100, 'multiplier': 1.15},
    'factory': {'name': '🏭 Factory', 'base_cost': 100000, 'base_income': 1000, 'multiplier': 1.15},
    'tech_startup': {'name': '💻 Tech Startup', 'base_cost': 1000000, 'base_income': 10000, 'multiplier': 1.15},
    'bank': {'name': '🏦 Bank', 'base_cost': 10000000, 'base_income': 100000, 'multiplier': 1.15},
    'oil_empire': {'name': '🛢️ Oil Empire', 'base_cost': 100000000, 'base_income': 1000000, 'multiplier': 1.15},
    'space_corp': {'name': '🚀 Space Corp', 'base_cost': 1000000000, 'base_income': 10000000, 'multiplier': 1.15},
}

UPGRADES = {
    'multiplier_1': {'name': '📈 Income Boost x2', 'cost': 5000, 'effect': 2},
    'multiplier_2': {'name': '📈 Income Boost x5', 'cost': 50000, 'effect': 5},
    'multiplier_3': {'name': '📈 Income Boost x10', 'cost': 500000, 'effect': 10},
    'multiplier_4': {'name': '📈 Income Boost x50', 'cost': 5000000, 'effect': 50},
    'multiplier_5': {'name': '📈 Income Boost x100', 'cost': 50000000, 'effect': 100},
}

def format_number(num):
    if num >= 1e12:
        return f"${num/1e12:.2f}T"
    elif num >= 1e9:
        return f"${num/1e9:.2f}B"
    elif num >= 1e6:
        return f"${num/1e6:.2f}M"
    elif num >= 1e3:
        return f"${num/1e3:.2f}K"
    else:
        return f"${num:.2f}"

def get_player(user_id):
    if user_id not in players:
        players[user_id] = {
            'money': 1000,
            'income_per_second': 0,
            'businesses': defaultdict(int),
            'upgrades': [],
            'income_multiplier': 1,
            'last_collect': datetime.now(),
            'total_earned': 0,
            'prestige_level': 0,
            'prestige_bonus': 1,
            'username': 'Unknown',
        }
    return players[user_id]

def calculate_business_cost(business_id, count):
    base = BUSINESSES[business_id]['base_cost']
    multiplier = BUSINESSES[business_id]['multiplier']
    return int(base * (multiplier ** count))

def calculate_income(player):
    total = 0
    for biz_id, count in player['businesses'].items():
        if count > 0:
            base_income = BUSINESSES[biz_id]['base_income']
            total += base_income * count
    total *= player['income_multiplier']
    total *= player['prestige_bonus']
    player['income_per_second'] = total
    return total

def collect_idle_income(player):
    now = datetime.now()
    time_diff = (now - player['last_collect']).total_seconds()
    time_diff = min(time_diff, 14400)
    idle_income = player['income_per_second'] * time_diff
    player['money'] += idle_income
    player['total_earned'] += idle_income
    player['last_collect'] = now
    return idle_income, time_diff

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    player['username'] = user.username or user.first_name
    idle_income, time_away = collect_idle_income(player)
    welcome_text = (
        "🔥 **WELCOME TO EMPIRE WARS** 🔥

"
        "Build your economic empire and DOMINATE the leaderboards!

"
        f"💰 **Your Stats:**
Money: {format_number(player['money'])}
"
        f"Income: {format_number(player['income_per_second'])}/sec
"
        f"Prestige Level: {player['prestige_level']}

"
    )
    if idle_income > 0:
        welcome_text += (
            f"💸 You earned {format_number(idle_income)} while you were away ({int(time_away/60)} minutes)!

"
        )
    welcome_text += (
        "**Commands:**
"
        "/empire - View your empire
"
        "/collect - Collect idle earnings
"
        "/leaderboard - See top players
"
        "/profile - Your detailed stats
"
        "Let's GET RICH! 💎"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def empire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    collect_idle_income(player)
    calculate_income(player)
    text = (
        "🏰 **YOUR EMPIRE** 🏰

"
        f"💰 Money: {format_number(player['money'])}
"
        f"📈 Income: {format_number(player['income_per_second'])}/sec
"
        f"⭐ Prestige: Level {player['prestige_level']} ({player['prestige_bonus']:.1f}x bonus)

"
        "**Your Businesses:**
"
    )
    if not player['businesses']:
        text += "
❌ No businesses yet! (feature in progress)
"
    else:
        for biz_id, count in player['businesses'].items():
            if count > 0:
                biz = BUSINESSES[biz_id]
                income = biz['base_income'] * count * player['income_multiplier'] * player['prestige_bonus']
                text += f"
{biz['name']}: x{count} ({format_number(income)}/sec)"
    text += f"

💸 Total Earned: {format_number(player['total_earned'])}"
    await update.message.reply_text(text, parse_mode='Markdown')

async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    idle_income, time_away = collect_idle_income(player)
    if idle_income > 0:
        text = (
            f"💰 **COLLECTED!**

+{format_number(idle_income)}
"
            f"You were away for {int(time_away/60)} minutes!"
        )
    else:
        text = "⏰ No idle income yet! Wait a bit."
    await update.message.reply_text(text, parse_mode='Markdown')

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global leaderboard_cache, last_leaderboard_update
    now = datetime.now()
    if (now - last_leaderboard_update).total_seconds() > 60:
        sorted_players = sorted(players.items(), key=lambda x: x[1]['total_earned'], reverse=True)
        leaderboard_cache = sorted_players[:10]
        last_leaderboard_update = now
    text = "🏆 **TOP 10 EMPIRES** 🏆

"
    if not leaderboard_cache:
        text += "No players yet! Be the first to dominate!
"
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, player) in enumerate(leaderboard_cache):
            medal = medals[i] if i < 3 else f"{i + 1}."
            text += (
                f"{medal} **{player['username']}**
"
                f"   💰 {format_number(player['total_earned'])} total earned
"
                f"   📈 {format_number(player['income_per_second'])}/sec

"
            )
    await update.message.reply_text(text, parse_mode='Markdown')

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    collect_idle_income(player)
    sorted_players = sorted(players.items(), key=lambda x: x[1]['total_earned'], reverse=True)
    rank = next((i + 1 for i, (uid, _) in enumerate(sorted_players) if uid == user.id), len(players))
    text = (
        "👤 **PLAYER PROFILE** 👤

"
        f"**{player['username']}**

"
        f"🏆 Rank: #{rank} / {len(players)}
"
        f"💰 Money: {format_number(player['money'])}
"
        f"📈 Income: {format_number(player['income_per_second'])}/sec
"
        f"💸 Total Earned: {format_number(player['total_earned'])}

"
        f"⭐ Prestige Level: {player['prestige_level']}
"
        f"🔥 Income Multiplier: {player['income_multiplier']}x
"
        f"🎯 Prestige Bonus: {player['prestige_bonus']}x
"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

def main():
    logging.basicConfig(level=logging.INFO)
    TOKEN = os.environ.get('BOT_TOKEN')
    if not TOKEN:
        print("❌ ERROR: BOT_TOKEN not found in environment variables!")
        return

    # Run Flask app in background thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Telegram bot handlers
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("empire", empire))
    application.add_handler(CommandHandler("collect", collect))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("profile", profile))

    print("🔥 EMPIRE WARS BOT IS RUNNING! 🔥")
    application.run_polling()

if __name__ == '__main__':
    main()
