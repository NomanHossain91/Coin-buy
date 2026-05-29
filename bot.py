import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))

COINS = {
    "niva_coin": {"name": "🟡 Niva Coin", "rate": 2.8, "per": 1000, "unit": "Coin"},
    "ns_follower": {"name": "👤 NS Follower", "rate": 6.0, "per": 1, "unit": "Follower"},
    "riva_coin": {"name": "🔵 Riva Coin", "rate": 2.8, "per": 1000, "unit": "Coin"},
    "top_coin": {"name": "🟠 Top Coin", "rate": 2.0, "per": 1000, "unit": "Coin"},
    "top_follower": {"name": "⭐ Top Follower", "rate": 2.4, "per": 1, "unit": "Follower"},
}

MINIMUM = 10000
ADMIN_USERNAME = "@nolab_coin_house"

PAYMENT_METHODS = {
    "bkash": "💳 bKash",
    "nagad": "💰 Nagad",
    "crypto": "🔗 Crypto (USDT/TRC20)",
}

SELECT_COIN, ENTER_AMOUNT, ENTER_PROOF, SELECT_PAYMENT, ENTER_PAYMENT_DETAILS = range(5)

user_data_store = {}

# ── /start ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 স্বাগতম, {user.first_name}!\n\n"
        f"🏪 *Nolab Coin House* এ আপনাকে স্বাগত!\n\n"
        f"এখানে আপনি আপনার coin/follower বিক্রি করতে পারবেন।\n\n"
        f"📌 *Minimum Sell:* {MINIMUM:,}\n\n"
        f"নিচের বাটনে চাপুন:"
    )
    keyboard = [
        [InlineKeyboardButton("💰 Coin বিক্রি করুন", callback_data="sell")],
        [InlineKeyboardButton("📊 রেট দেখুন", callback_data="rates")],
    ]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── Rate list ────────────────────────────────────────────────
async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📊 *বর্তমান রেট তালিকা:*\n\n"
    for key, coin in COINS.items():
        if coin["per"] == 1:
            text += f"{coin['name']}\n   ➡️ প্রতিটি = {coin['rate']} টাকা\n\n"
        else:
            text += f"{coin['name']}\n   ➡️ প্রতি {coin['per']:,} = {coin['rate']} টাকা\n\n"
    text += f"📌 Minimum: {MINIMUM:,} | Admin: {ADMIN_USERNAME}"
    keyboard = [[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")]]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))

# ── Sell → Select Coin ──────────────────────────────────────
async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "🪙 *কোন Coin/Follower বিক্রি করতে চান?*\n\nনিচ থেকে সিলেক্ট করুন:"
    keyboard = []
    for key, coin in COINS.items():
        if coin["per"] == 1:
            label = f"{coin['name']} — {coin['rate']} টাকা/টি"
        else:
            label = f"{coin['name']} — {coin['rate']} টাকা/{coin['per']:,}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"coin_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")])
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_COIN

# ── Coin selected ────────────────────────────────────────────
async def coin_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    coin_key = query.data.replace("coin_", "")

    # BUG FIX: invalid coin key crash থেকে রক্ষা
    if coin_key not in COINS:
        await query.edit_message_text("❌ ভুল selection। /start দিন।")
        return ConversationHandler.END

    coin = COINS[coin_key]
    user_id = query.from_user.id
    user_data_store[user_id] = {"coin_key": coin_key, "coin": coin}

    text = (
        f"✅ সিলেক্ট করেছেন: *{coin['name']}*\n\n"
        f"💵 রেট: {coin['rate']} টাকা প্রতি {coin['per']:,} {coin['unit']}\n"
        f"📌 Minimum: {MINIMUM:,}\n\n"
        f"কতটি {coin['unit']} বিক্রি করতে চান লিখুন:\n"
        f"_শুধু সংখ্যা, যেমন: 50000_"
    )
    await query.edit_message_text(text, parse_mode="Markdown")
    return ENTER_AMOUNT

# ── Amount entered ───────────────────────────────────────────
async def amount_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # BUG FIX: user_data_store এ data না থাকলে crash
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session শেষ হয়ে গেছে। /start দিন।")
        return ConversationHandler.END

    text = update.message.text.strip().replace(",", "").replace(".", "")

    if not text.isdigit():
        await update.message.reply_text("❌ শুধু সংখ্যা লিখুন! আবার চেষ্টা করুন:")
        return ENTER_AMOUNT

    amount = int(text)
    coin = user_data_store[user_id]["coin"]

    if amount < MINIMUM:
        await update.message.reply_text(
            f"❌ Minimum {MINIMUM:,} {coin['unit']} হতে হবে!\nআবার লিখুন:"
        )
        return ENTER_AMOUNT

    if coin["per"] == 1:
        total = amount * coin["rate"]
    else:
        total = (amount / coin["per"]) * coin["rate"]

    user_data_store[user_id]["amount"] = amount
    user_data_store[user_id]["total"] = round(total, 2)

    text = (
        f"✅ পরিমাণ: *{amount:,} {coin['unit']}*\n"
        f"💰 আপনি পাবেন: *{total:.2f} টাকা*\n\n"
        f"এখন *{ADMIN_USERNAME}* তে coin পাঠান।\n\n"
        f"পাঠানো হলে *স্ক্রিনশট* পাঠান:"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    return ENTER_PROOF

# ── Proof received ───────────────────────────────────────────
async def proof_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # BUG FIX: session check
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session শেষ। /start দিন।")
        return ConversationHandler.END

    if update.message.photo:
        user_data_store[user_id]["proof_file_id"] = update.message.photo[-1].file_id
        user_data_store[user_id]["proof_type"] = "photo"
    elif update.message.text:
        user_data_store[user_id]["proof_file_id"] = update.message.text
        user_data_store[user_id]["proof_type"] = "text"
    else:
        await update.message.reply_text("❌ স্ক্রিনশট বা Transaction ID পাঠান!")
        return ENTER_PROOF

    keyboard = [
        [InlineKeyboardButton("💳 bKash", callback_data="pay_bkash")],
        [InlineKeyboardButton("💰 Nagad", callback_data="pay_nagad")],
        [InlineKeyboardButton("🔗 Crypto (USDT/TRC20)", callback_data="pay_crypto")],
    ]
    await update.message.reply_text(
        "✅ প্রমাণ পেয়েছি!\n\n💳 *Payment Method সিলেক্ট করুন:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_PAYMENT

# ── Payment method ───────────────────────────────────────────
async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # BUG FIX: session check
    if user_id not in user_data_store:
        await query.edit_message_text("❌ Session শেষ। /start দিন।")
        return ConversationHandler.END

    method = query.data.replace("pay_", "")
    user_data_store[user_id]["payment_method"] = method

    if method == "bkash":
        text = "📱 আপনার *bKash নম্বর* দিন:\n_যে নম্বরে টাকা পাঠাবো_"
    elif method == "nagad":
        text = "📱 আপনার *Nagad নম্বর* দিন:\n_যে নম্বরে টাকা পাঠাবো_"
    else:
        text = "🔗 আপনার *USDT TRC20 Wallet Address* দিন:"

    await query.edit_message_text(text, parse_mode="Markdown")
    return ENTER_PAYMENT_DETAILS

# ── Submit order ─────────────────────────────────────────────
async def payment_details_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    details = update.message.text.strip()
    data = user_data_store.get(user_id, {})

    if not data:
        await update.message.reply_text("❌ Session শেষ। /start দিন।")
        return ConversationHandler.END

    data["payment_details"] = details
    coin = data["coin"]
    method_name = PAYMENT_METHODS.get(data.get("payment_method", ""), "Unknown")

    confirm_text = (
        f"✅ *অর্ডার Submit হয়েছে!*\n\n"
        f"🪙 Coin: {coin['name']}\n"
        f"📦 পরিমাণ: {data['amount']:,} {coin['unit']}\n"
        f"💰 পাবেন: {data['total']:.2f} টাকা\n"
        f"💳 Payment: {method_name}\n"
        f"📋 Account: `{details}`\n\n"
        f"⏳ Admin verify করার পর টাকা পাঠানো হবে।"
    )
    await update.message.reply_text(confirm_text, parse_mode="Markdown")

    admin_text = (
        f"🔔 *নতুন Sell অর্ডার!*\n\n"
        f"👤 User: {user.first_name}\n"
        f"🆔 User ID: `{user_id}`\n"
        f"🪙 Coin: {coin['name']}\n"
        f"📦 পরিমাণ: {data['amount']:,} {coin['unit']}\n"
        f"💰 দিতে হবে: {data['total']:.2f} টাকা\n"
        f"💳 Payment: {method_name}\n"
        f"📋 Account: `{details}`"
    )
    keyboard = [[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"),
    ]]

    try:
        if data.get("proof_type") == "photo":
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=data["proof_file_id"],
                caption=admin_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text + f"\n📎 Proof: {data.get('proof_file_id', 'N/A')}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Admin notify error: {e}")

    # BUG FIX: order শেষে data clear করো
    user_data_store.pop(user_id, None)
    return ConversationHandler.END

# ── Admin Approve/Reject ─────────────────────────────────────
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # BUG FIX: query.answer() আগে call করো, তারপর permission check
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ আপনি Admin না!", show_alert=True)
        return

    parts = query.data.split("_", 1)
    if len(parts) != 2:
        return

    action, target_user_id_str = parts
    try:
        target_user_id = int(target_user_id_str)
    except ValueError:
        return

    if action == "approve":
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    "✅ *আপনার অর্ডার Approved!*\n\n"
                    "টাকা পাঠানো হয়েছে।\n"
                    "ধন্যবাদ! আবার বিক্রি করতে /start দিন।"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(e)

        # BUG FIX: photo হলে edit_message_caption, text হলে edit_message_text
        try:
            if query.message.caption:
                await query.edit_message_caption(
                    caption=query.message.caption + "\n\n✅ APPROVED",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    query.message.text + "\n\n✅ APPROVED",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(e)

    elif action == "reject":
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"❌ *আপনার অর্ডার Reject হয়েছে।*\n\n"
                    f"কারণ জানতে যোগাযোগ করুন: {ADMIN_USERNAME}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(e)

        # BUG FIX: same fix for reject
        try:
            if query.message.caption:
                await query.edit_message_caption(
                    caption=query.message.caption + "\n\n❌ REJECTED",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    query.message.text + "\n\n❌ REJECTED",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(e)

# ── Back home ────────────────────────────────────────────────
async def back_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("💰 Coin বিক্রি করুন", callback_data="sell")],
        [InlineKeyboardButton("📊 রেট দেখুন", callback_data="rates")],
    ]
    await query.edit_message_text(
        "🏪 *Nolab Coin House*\n\nনিচের বাটনে চাপুন:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_store.pop(user_id, None)  # BUG FIX: cancel এ data clear
    await update.message.reply_text("❌ বাতিল হয়েছে। /start দিয়ে আবার শুরু করুন।")
    return ConversationHandler.END

# ── Main ─────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(sell_start, pattern="^sell$")],
        states={
            SELECT_COIN: [CallbackQueryHandler(coin_selected, pattern="^coin_")],
            ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_entered)],
            ENTER_PROOF: [
                MessageHandler(filters.PHOTO, proof_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, proof_received),
            ],
            SELECT_PAYMENT: [CallbackQueryHandler(payment_selected, pattern="^pay_")],
            ENTER_PAYMENT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_details_entered)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        # BUG FIX: conversation timeout ও per_message
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(show_rates, pattern="^rates$"))
    app.add_handler(CallbackQueryHandler(back_home, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    print("Bot চালু হয়েছে!")
    app.run_polling(drop_pending_updates=True)  # BUG FIX: old updates ignore

if __name__ == "__main__":
    main()
