import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime, timedelta
from collections import defaultdict
import random
from threading import Thread
from flask import Flask
import os

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory database (replace with real DB for production)
players = {}
leaderboard_cache = []
last_leaderboard_update = datetime.now()

# Game constants
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
            'raids_won': 0,
            'raids_lost': 0,
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
    welcome_text = f"""
🔥 **WELCOME TO EMPIRE WARS** 🔥

Build your economic empire and DOMINATE the leaderboards!

💰 **Your Stats:**
Money: {format_number(player['money'])}
Income: {format_number(player['income_per_second'])}/sec
Prestige Level: {player['prestige_level']}
"""
    if idle_income > 0:
        welcome_text += f"💸 You earned {format_number(idle_income)} while you were away ({int(time_away/60)} minutes)!

"
    welcome_text += """
**Commands:**
/empire - View your empire
/buy - Buy businesses
/upgrade - Buy upgrades
/collect - Collect idle earnings
/leaderboard - See top players
/profile - Your detailed stats
/raid - Attack other players (coming soon!)

Let's GET RICH! 💎
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def empire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    idle_income, _ = collect_idle_income(player)
    calculate_income(player)
    text = f"""
🏰 **YOUR EMPIRE** 🏰

💰 Money: {format_number(player['money'])}
📈 Income: {format_number(player['income_per_second'])}/sec
⭐ Prestige: Level {player['prestige_level']} ({player['prestige_bonus']:.1f}x bonus)

**Your Businesses:**
"""
    if not player['businesses']:
        text += "
❌ No businesses yet! Use /buy to start building!
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
    keyboard = [
        [InlineKeyboardButton("💰 Collect", callback_data='collect'),
         InlineKeyboardButton("🏪 Buy", callback_data='buy_menu')],
        [InlineKeyboardButton("📈 Upgrades", callback_data='upgrade_menu'),
         InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = get_player(user.id)
    text = "🏪 **BUY BUSINESSES** 🏪

💰 Your Money: " + format_number(player['money']) + "

"
    keyboard = []
    for biz_id, biz in BUSINESSES.items():
        count = player['businesses'][biz_id]
        cost = calculate_business_cost(biz_id, count)
        income = biz['base_income'] * player['income_multiplier'] * player['prestige_bonus']
        can_afford = "✅" if player['money'] >= cost else "❌"
        button_text = f"{can_afford} {biz['name']} | {format_number(cost)}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'buy_{biz_id}')])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_empire')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def buy_business(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = get_player(user.id)
    biz_id = query.data.replace('buy_', '')
    count = player['businesses'][biz_id]
    cost = calculate_business_cost(biz_id, count)
    if player['money'] >= cost:
        player['money'] -= cost
        player['businesses'][biz_id] += 1
        calculate_income(player)
        biz = BUSINESSES[biz_id]
        await query.answer(f"🎉 Bought {biz['name']}! +{format_number(biz['base_income'])}/sec", show_alert=True)
        await buy_menu(update, context)
    else:
        await query.answer("❌ Not enough money!", show_alert=True)

async def upgrade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = get_player(user.id)
    text = f"📈 **UPGRADES** 📈

💰 Your Money: {format_number(player['money'])}

"
    text += f"Current Multiplier: {player['income_multiplier']}x

"
    keyboard = []
    for upg_id, upg in UPGRADES.items():
        if upg_id not in player['upgrades']:
            can_afford = "✅" if player['money'] >= upg['cost'] else "❌"
            button_text = f"{can_afford} {upg['name']} | {format_number(upg['cost'])}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'upg_{upg_id}')])
    if not keyboard:
        text += "🎉 You bought all upgrades! More coming soon!"
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_empire')])
    else:
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_empire')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def buy_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = get_player(user.id)
    upg_id = query.data.replace('upg_', '')
    upg = UPGRADES[upg_id]
    if upg_id not in player['upgrades'] and player['money'] >= upg['cost']:
        player['money'] -= upg['cost']
        player['upgrades'].append(upg_id)
        player['income_multiplier'] *= upg['effect']
        calculate_income(player)
        await query.answer(f"🚀 UPGRADE PURCHASED! Income multiplier now {player['income_multiplier']}x!", show_alert=True)
        await upgrade_menu(update, context)
    else:
        await query.answer("❌ Cannot buy this upgrade!", show_alert=True)

async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user = query.from_user
    else:
        user = update.effective_user
    player = get_player(user.id)
    idle_income, time_away = collect_idle_income(player)
    if idle_income > 0:
        text = f"💰 **COLLECTED!**

+{format_number(idle_income)}

You were away for {int(time_away/60)} minutes!"
        if query:
            await query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(text, parse_mode='Markdown')
    else:
        msg = "⏰ No idle income yet! Wait a bit."
        if query:
            await query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)

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
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} **{player['username']}**
"
            text += f"   💰 {format_number(player['total_earned'])} total earned
"
            text += f"   📈 {format_number(player['income_per_second'])}/sec

"
    if update.callback_query:
        await update.callback_query.answer()
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data='back_empire')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user.id)
    collect_idle_income(player)
    sorted_players = sorted(players.items(), key=lambda x: x[1]['total_earned'], reverse=True)
    rank = next((i+1 for i, (uid, _) in enumerate(sorted_players) if uid == user.id), len(players))
    text = f"""
👤 **PLAYER PROFILE** 👤

**{player['username']}**

🏆 Rank: #{rank} / {len(players)}
💰 Money: {format_number(player['money'])}
📈 Income: {format_number(player['income_per_second'])}/sec
💸 Total Earned: {format_number(player['total_earned'])}

⭐ Prestige Level: {player['prestige_level']}
🔥 Income Multiplier: {player['income_multiplier']}x
🎯 Prestige Bonus: {player['prestige_bonus']}x

**Businesses Owned:**
"""
    total_businesses = sum(player['businesses'].values())
    text += f"Total: {total_businesses}

"
    for biz_id, count in player['businesses'].items():
        if count > 0:
            text += f"{BUSINESSES[biz_id]['name']}: x{count}
"
    await update.message.reply_text(text, parse_mode='Markdown')

async def back_to_empire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    player = get_player(user.id)
    calculate_income(player)
    text = f"""
🏰 **YOUR EMPIRE** 🏰

💰 Money: {format_number(player['money'])}
📈 Income: {format_number(player['income_per_second'])}/sec
⭐ Prestige: Level {player['prestige_level']}

**Your Businesses:**
"""
    if not player['businesses']:
        text += "
❌ No businesses yet!
"
    else:
        for biz_id, count in player['businesses'].items():
            if count > 0:
                text += f"
{BUSINESSES[biz_id]['name']}: x{count}"
    keyboard = [
        [InlineKeyboardButton("💰 Collect", callback_data='collect'),
         InlineKeyboardButton("🏪 Buy", callback_data='buy_menu')],
        [InlineKeyboardButton("📈 Upgrades", callback_data='upgrade_menu'),
         InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Flask app to keep Render happy
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

def main():
    # ---- PUT YOUR TELEGRAM BOT TOKEN BELOW ----
    TOKEN = "8270525102:AAFUJfnx3GwlFk42lN4MbOqpZgE0SssxA7A"
    if not TOKEN:
        print("❌ ERROR: BOT_TOKEN not found!")
        return
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("empire", empire))
    application.add_handler(CommandHandler("collect", collect))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CallbackQueryHandler(buy_menu, pattern='^buy_menu$'))
    application.add_handler(CallbackQueryHandler(buy_business, pattern='^buy_'))
    application.add_handler(CallbackQueryHandler(upgrade_menu, pattern='^upgrade_menu$'))
    application.add_handler(CallbackQueryHandler(buy_upgrade, pattern='^upg_'))
    application.add_handler(CallbackQueryHandler(collect, pattern='^collect$'))
    application.add_handler(CallbackQueryHandler(leaderboard, pattern='^leaderboard$'))
    application.add_handler(CallbackQueryHandler(back_to_empire, pattern='^back_empire$'))
    print("🔥 EMPIRE WARS BOT IS RUNNING! 🔥")
    application.run_polling()

if __name__ == '__main__':
    main()
