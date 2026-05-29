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
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))  # তোমার Telegram ID

# Coin rates
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

# Conversation states
SELECT_COIN, ENTER_AMOUNT, ENTER_PROOF, SELECT_PAYMENT, ENTER_PAYMENT_DETAILS = range(5)

# Temporary storage (in production use a database)
user_data_store = {}

# ─── /start ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 স্বাগতম, {user.first_name}!\n\n"
        f"🏪 *Nolab Coin House* - এ আপনাকে স্বাগত!\n\n"
        f"এখানে আপনি আপনার coin/follower বিক্রি করতে পারবেন।\n\n"
        f"📌 *Minimum Sell:* {MINIMUM:,} (যেকোনো coin/follower)\n\n"
        f"নিচের বাটনে চাপুন:"
    )
    keyboard = [
        [InlineKeyboardButton("💰 Coin বিক্রি করুন", callback_data="sell")],
        [InlineKeyboardButton("📊 রেট দেখুন", callback_data="rates")],
        [InlineKeyboardButton("📜 আমার অর্ডার", callback_data="my_orders")],
    ]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── Rate list ────────────────────────────────────────────
async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📊 *বর্তমান রেট তালিকা:*\n\n"
    for key, coin in COINS.items():
        if coin["per"] == 1:
            text += f"{coin['name']}\n   ➡️ প্রতিটি = ৳{coin['rate']}\n\n"
        else:
            text += f"{coin['name']}\n   ➡️ প্রতি {coin['per']:,} = ৳{coin['rate']}\n\n"
    text += f"📌 Minimum: {MINIMUM:,} | Admin: {ADMIN_USERNAME}"
    keyboard = [[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")]]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))

# ─── Sell → Select Coin ───────────────────────────────────
async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "🪙 *কোন Coin/Follower বিক্রি করতে চান?*\n\nনিচ থেকে সিলেক্ট করুন:"
    keyboard = []
    for key, coin in COINS.items():
        if coin["per"] == 1:
            label = f"{coin['name']} — ৳{coin['rate']}/টি"
        else:
            label = f"{coin['name']} — ৳{coin['rate']}/{coin['per']:,}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"coin_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")])
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_COIN

# ─── Coin selected → Enter Amount ─────────────────────────
async def coin_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    coin_key = query.data.replace("coin_", "")
    coin = COINS[coin_key]
    user_id = query.from_user.id
    user_data_store[user_id] = {"coin_key": coin_key, "coin": coin}

    text = (
        f"✅ সিলেক্ট করেছেন: *{coin['name']}*\n\n"
        f"💵 রেট: ৳{coin['rate']} প্রতি {coin['per']:,} {coin['unit']}\n"
        f"📌 Minimum: {MINIMUM:,}\n\n"
        f"এখন আপনি কতটি {coin['unit']} বিক্রি করতে চান সেটি লিখুন:\n"
        f"_(শুধু সংখ্যা লিখুন, যেমন: 50000)_"
    )
    await query.edit_message_text(text, parse_mode="Markdown")
    return ENTER_AMOUNT

# ─── Amount entered ───────────────────────────────────────
async def amount_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().replace(",", "")

    if not text.isdigit():
        await update.message.reply_text("❌ শুধু সংখ্যা লিখুন! আবার চেষ্টা করুন:")
        return ENTER_AMOUNT

    amount = int(text)
    if amount < MINIMUM:
        await update.message.reply_text(
            f"❌ Minimum {MINIMUM:,} {user_data_store[user_id]['coin']['unit']} হতে হবে!\n"
            f"আবার লিখুন:"
        )
        return ENTER_AMOUNT

    coin = user_data_store[user_id]["coin"]
    if coin["per"] == 1:
        total = amount * coin["rate"]
    else:
        total = (amount / coin["per"]) * coin["rate"]

    user_data_store[user_id]["amount"] = amount
    user_data_store[user_id]["total"] = round(total, 2)

    text = (
        f"✅ পরিমাণ: *{amount:,} {coin['unit']}*\n"
        f"💰 আপনি পাবেন: *৳{total:.2f}*\n\n"
        f"এখন *{ADMIN_USERNAME}* -এ coin পাঠান।\n\n"
        f"পাঠানো হলে *স্ক্রিনশট* পাঠান প্রমাণ হিসেবে:"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    return ENTER_PROOF

# ─── Screenshot/Proof ─────────────────────────────────────
async def proof_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.message.photo:
        user_data_store[user_id]["proof_file_id"] = update.message.photo[-1].file_id
        user_data_store[user_id]["proof_type"] = "photo"
    elif update.message.text:
        user_data_store[user_id]["proof_file_id"] = update.message.text
        user_data_store[user_id]["proof_type"] = "text"
    else:
        await update.message.reply_text("❌ স্ক্রিনশট বা Transaction ID পাঠান!")
        return ENTER_PROOF

    text = "✅ প্রমাণ পেয়েছি!\n\n💳 *Payment Method সিলেক্ট করুন:*"
    keyboard = [
        [InlineKeyboardButton("💳 bKash", callback_data="pay_bkash")],
        [InlineKeyboardButton("💰 Nagad", callback_data="pay_nagad")],
        [InlineKeyboardButton("🔗 Crypto (USDT/TRC20)", callback_data="pay_crypto")],
    ]
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_PAYMENT

# ─── Payment method selected ──────────────────────────────
async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    method = query.data.replace("pay_", "")
    user_data_store[user_id]["payment_method"] = method

    if method == "bkash":
        text = "📱 আপনার *bKash নম্বর* দিন:\n_(যে নম্বরে টাকা পাঠাবো)_"
    elif method == "nagad":
        text = "📱 আপনার *Nagad নম্বর* দিন:\n_(যে নম্বরে টাকা পাঠাবো)_"
    else:
        text = "🔗 আপনার *USDT (TRC20) Wallet Address* দিন:"

    await query.edit_message_text(text, parse_mode="Markdown")
    return ENTER_PAYMENT_DETAILS

# ─── Payment details → Submit order ───────────────────────
async def payment_details_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    details = update.message.text.strip()
    data = user_data_store.get(user_id, {})

    if not data:
        await update.message.reply_text("❌ কিছু একটা সমস্যা হয়েছে। /start দিন।")
        return ConversationHandler.END

    data["payment_details"] = details
    coin = data["coin"]
    method_name = PAYMENT_METHODS.get(data["payment_method"], data["payment_method"])

    # Confirm to user
    confirm_text = (
        f"✅ *অর্ডার Submit হয়েছে!*\n\n"
        f"🪙 Coin: {coin['name']}\n"
        f"📦 পরিমাণ: {data['amount']:,} {coin['unit']}\n"
        f"💰 পাবেন: ৳{data['total']:.2f}\n"
        f"💳 Payment: {method_name}\n"
        f"📋 Account: `{details}`\n\n"
        f"⏳ Admin verify করার পর টাকা পাঠানো হবে।\n"
        f"সাধারণত ১-২৪ ঘণ্টার মধ্যে।"
    )
    await update.message.reply_text(confirm_text, parse_mode="Markdown")

    # Notify admin
    admin_text = (
        f"🔔 *নতুন Sell অর্ডার!*\n\n"
        f"👤 User: [{user.first_name}](tg://user?id={user_id})\n"
        f"🆔 User ID: `{user_id}`\n"
        f"🪙 Coin: {coin['name']}\n"
        f"📦 পরিমাণ: {data['amount']:,} {coin['unit']}\n"
        f"💰 দিতে হবে: ৳{data['total']:.2f}\n"
        f"💳 Payment: {method_name}\n"
        f"📋 Account: `{details}`"
    )
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"),
        ]
    ]
    # Send proof to admin
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
            full_admin = admin_text + f"\n📎 Proof: {data.get('proof_file_id', 'N/A')}"
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=full_admin,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Admin notify error: {e}")

    return ConversationHandler.END

# ─── Admin Approve/Reject ─────────────────────────────────
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ আপনি Admin না!", show_alert=True)
        return

    action, target_user_id = query.data.split("_", 1)
    target_user_id = int(target_user_id)
    data = user_data_store.get(target_user_id, {})

    if action == "approve":
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"✅ *আপনার অর্ডার Approved!*\n\n"
                    f"💰 ৳{data.get('total', '?'):.2f} পাঠানো হয়েছে।\n"
                    f"ধন্যবাদ! আবার বিক্রি করতে /start দিন।"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(e)
        await query.edit_message_caption(
            query.message.caption + "\n\n✅ *APPROVED by Admin*",
            parse_mode="Markdown"
        )

    elif action == "reject":
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"❌ *আপনার অর্ডার Reject হয়েছে।*\n\n"
                    f"কারণ জানতে Admin-এ যোগাযোগ করুন: {ADMIN_USERNAME}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(e)
        try:
            await query.edit_message_caption(
                query.message.caption + "\n\n❌ *REJECTED by Admin*",
                parse_mode="Markdown"
            )
        except:
            await query.edit_message_text(
                query.message.text + "\n\n❌ *REJECTED by Admin*",
                parse_mode="Markdown"
            )

# ─── Back to home ─────────────────────────────────────────
async def back_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🏪 *Nolab Coin House*\n\n"
        "নিচের বাটনে চাপুন:"
    )
    keyboard = [
        [InlineKeyboardButton("💰 Coin বিক্রি করুন", callback_data="sell")],
        [InlineKeyboardButton("📊 রেট দেখুন", callback_data="rates")],
        [InlineKeyboardButton("📜 আমার অর্ডার", callback_data="my_orders")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📜 অর্ডার হিস্ট্রি শীঘ্রই আসছে!\n\nএখন Admin এর সাথে যোগাযোগ করুন: " + ADMIN_USERNAME,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_home")]])
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল হয়েছে। /start দিয়ে আবার শুরু করুন।")
    return ConversationHandler.END

# ─── Main ─────────────────────────────────────────────────
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
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(show_rates, pattern="^rates$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(back_home, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    print("✅ Bot চালু হয়েছে!")
    app.run_polling()

if __name__ == "__main__":
    main()
