import subprocess
import sys
# Force correct version at runtime — prevents Railway v21+ crash
subprocess.run(
    [sys.executable, "-m", "pip", "install", "python-telegram-bot==20.7", "-q"],
    check=False
)

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

COINS = {
    "niva_coin":    {"name": "Niva Coin",    "rate": 2.8, "per": 1000, "unit": "Coin"},
    "ns_follower":  {"name": "NS Follower",  "rate": 6.0, "per": 1,    "unit": "Follower"},
    "riva_coin":    {"name": "Riva Coin",    "rate": 2.8, "per": 1000, "unit": "Coin"},
    "top_coin":     {"name": "Top Coin",     "rate": 2.0, "per": 1000, "unit": "Coin"},
    "top_follower": {"name": "Top Follower", "rate": 2.4, "per": 1,    "unit": "Follower"},
}

MINIMUM_COIN = 10000      # minimum coins to sell
MINIMUM_FOLLOWER = 100    # minimum followers to sell (10000 followers is unrealistic)
ADMIN_USERNAME = "@nolab_coin_house"

PAYMENT_METHODS = {
    "bkash":  "bKash",
    "nagad":  "Nagad",
    "crypto": "Crypto USDT/TRC20",
}

SELECT_COIN, ENTER_AMOUNT, ENTER_PROOF, SELECT_PAYMENT, ENTER_PAYMENT_DETAILS = range(5)

# In-memory session store
store = {}

# Session TTL: auto-clear abandoned sessions after 30 minutes
import time
SESSION_TTL = 1800  # 30 minutes in seconds


def home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Coin বিক্রি করুন", callback_data="sell")],
        [InlineKeyboardButton("রেট দেখুন", callback_data="rates")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Clear any leftover session on /start
    store.pop(update.effective_user.id, None)
    user = update.effective_user
    await update.message.reply_text(
        f"স্বাগতম {user.first_name}!\n\n"
        f"Nolab Coin House এ আপনাকে স্বাগত!\n"
        f"Minimum Coin: {MINIMUM_COIN:,} | Minimum Follower: {MINIMUM_FOLLOWER:,}\n\n"
        f"নিচের বাটনে চাপুন:",
        reply_markup=home_keyboard()
    )


async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "বর্তমান রেট:\n\n"
    for coin in COINS.values():
        if coin["per"] == 1:
            text += f"• {coin['name']}: {coin['rate']} টাকা/টি\n"
        else:
            text += f"• {coin['name']}: {coin['rate']} টাকা/{coin['per']:,}\n"
    text += f"\nMin Coin: {MINIMUM_COIN:,} | Min Follower: {MINIMUM_FOLLOWER:,}\nযোগাযোগ: {ADMIN_USERNAME}"
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 ফিরে যান", callback_data="back_home")]
        ])
    )


async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = []
    for key, coin in COINS.items():
        if coin["per"] == 1:
            label = f"{coin['name']} — {coin['rate']} টাকা/টি"
        else:
            label = f"{coin['name']} — {coin['rate']} টাকা/{coin['per']:,}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"coin_{key}")])
    keyboard.append([InlineKeyboardButton("🏠 ফিরে যান", callback_data="back_home")])
    await query.edit_message_text(
        "কোন Coin বিক্রি করতে চান?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_COIN


async def coin_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    coin_key = query.data[5:]
    if coin_key not in COINS:
        await query.edit_message_text("ভুল নির্বাচন। /start দিন।")
        return ConversationHandler.END
    coin = COINS[coin_key]
    user_id = query.from_user.id
    store[user_id] = {"coin_key": coin_key, "coin": coin, "_ts": time.time()}
    await query.edit_message_text(
        f"✅ সিলেক্ট: {coin['name']}\n"
        f"রেট: {coin['rate']} টাকা প্রতি {coin['per']:,} {coin['unit']}\n"
        f"Minimum: {MINIMUM_FOLLOWER if coin['unit'] == 'Follower' else MINIMUM_COIN:,}\n\n"
        f"কতটি {coin['unit']} বিক্রি করবেন?\n(শুধু সংখ্যা লিখুন, যেমন: 50000)"
    )
    return ENTER_AMOUNT


async def amount_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in store:
        await update.message.reply_text("Session শেষ হয়ে গেছে। /start দিন।")
        return ConversationHandler.END

    text = update.message.text.strip().replace(",", "").replace(".", "").replace(" ", "")
    if not text.isdigit():
        await update.message.reply_text("❌ শুধু সংখ্যা লিখুন! আবার চেষ্টা করুন:")
        return ENTER_AMOUNT

    amount = int(text)
    coin = store[user_id]["coin"]

    minimum = MINIMUM_FOLLOWER if coin["unit"] == "Follower" else MINIMUM_COIN
    if amount < minimum:
        await update.message.reply_text(
            f"❌ Minimum {minimum:,} {coin['unit']} হতে হবে!\nআবার লিখুন:"
        )
        return ENTER_AMOUNT

    total = (amount * coin["rate"]) if coin["per"] == 1 else (amount / coin["per"]) * coin["rate"]
    store[user_id]["amount"] = amount
    store[user_id]["total"] = round(total, 2)

    await update.message.reply_text(
        f"💰 পরিমাণ: {amount:,} {coin['unit']}\n"
        f"✅ আপনি পাবেন: {total:.2f} টাকা\n\n"
        f"এখন {ADMIN_USERNAME} তে coin পাঠান।\n"
        f"পাঠানোর পর স্ক্রিনশট বা Transaction ID পাঠান:"
    )
    return ENTER_PROOF


async def proof_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in store:
        await update.message.reply_text("Session শেষ হয়ে গেছে। /start দিন।")
        return ConversationHandler.END

    if update.message.photo:
        store[user_id]["proof_file_id"] = update.message.photo[-1].file_id
        store[user_id]["proof_type"] = "photo"
    elif update.message.text and update.message.text.strip():
        store[user_id]["proof_file_id"] = update.message.text.strip()
        store[user_id]["proof_type"] = "text"
    else:
        await update.message.reply_text("❌ স্ক্রিনশট বা Transaction ID পাঠান!")
        return ENTER_PROOF

    await update.message.reply_text(
        "✅ প্রমাণ পেয়েছি!\n\nPayment Method সিলেক্ট করুন:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("bKash", callback_data="pay_bkash")],
            [InlineKeyboardButton("Nagad", callback_data="pay_nagad")],
            [InlineKeyboardButton("Crypto (USDT/TRC20)", callback_data="pay_crypto")],
        ])
    )
    return SELECT_PAYMENT


async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in store:
        await query.edit_message_text("Session শেষ হয়ে গেছে। /start দিন।")
        return ConversationHandler.END

    method = query.data[4:]
    store[user_id]["payment_method"] = method

    prompts = {
        "bkash":  "আপনার bKash নম্বর দিন (যেমন: 01XXXXXXXXX):",
        "nagad":  "আপনার Nagad নম্বর দিন (যেমন: 01XXXXXXXXX):",
        "crypto": "আপনার USDT TRC20 Wallet Address দিন:",
    }
    await query.edit_message_text(prompts.get(method, "Account details দিন:"))
    return ENTER_PAYMENT_DETAILS


async def payment_details_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    details = update.message.text.strip()

    data = store.get(user_id)
    if not data:
        await update.message.reply_text("Session শেষ হয়ে গেছে। /start দিন।")
        return ConversationHandler.END

    if not details:
        await update.message.reply_text("❌ Account details লিখুন!")
        return ENTER_PAYMENT_DETAILS

    data["payment_details"] = details
    coin = data["coin"]
    method_name = PAYMENT_METHODS.get(data.get("payment_method", ""), "Unknown")

    # Confirm to user
    await update.message.reply_text(
        f"✅ অর্ডার Submit হয়েছে!\n\n"
        f"Coin: {coin['name']}\n"
        f"পরিমাণ: {data['amount']:,} {coin['unit']}\n"
        f"পাবেন: {data['total']:.2f} টাকা\n"
        f"Payment: {method_name}\n"
        f"Account: {details}\n\n"
        f"Admin verify করার পর টাকা পাঠানো হবে। ধন্যবাদ! 🙏"
    )

    # Notify admin
    admin_text = (
        f"🔔 নতুন Sell অর্ডার!\n\n"
        f"👤 User: {user.first_name}"
        + (f" (@{user.username})" if user.username else "") +
        f"\n🆔 User ID: {user_id}\n"
        f"💎 Coin: {coin['name']}\n"
        f"📦 পরিমাণ: {data['amount']:,} {coin['unit']}\n"
        f"💵 দিতে হবে: {data['total']:.2f} টাকা\n"
        f"💳 Payment: {method_name}\n"
        f"📱 Account: {details}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"),
    ]])

    try:
        if data.get("proof_type") == "photo":
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=data["proof_file_id"],
                caption=admin_text,
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text + f"\n📎 Proof: {data.get('proof_file_id', 'N/A')}",
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Admin notify error: {e}")

    store.pop(user_id, None)
    return ConversationHandler.END


async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # BUGFIX: Check admin before answering to avoid silent failures
    if query.from_user.id != ADMIN_ID:
        await query.answer("আপনি Admin না!", show_alert=True)
        return

    await query.answer()

    # BUGFIX: Use maxsplit=1 to safely split "approve_12345678" or "reject_12345678"
    parts = query.data.split("_", 1)
    if len(parts) != 2:
        logger.error(f"Unexpected callback data: {query.data}")
        return

    action, uid_str = parts
    try:
        target_id = int(uid_str)
    except ValueError:
        logger.error(f"Invalid user ID in callback: {uid_str}")
        return

    original_text = query.message.caption or query.message.text or ""
    is_photo = bool(query.message.caption)
    # Telegram limits: caption=1024 chars, text message=4096 chars
    MAX_CAP = 1024 if is_photo else 4096

    if action == "approve":
        suffix = "\n\n✅ APPROVED"
        safe_text = original_text[: MAX_CAP - len(suffix)] + suffix
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="✅ আপনার অর্ডার Approved!\nটাকা পাঠানো হয়েছে। ধন্যবাদ! 🙏"
            )
        except Exception as e:
            logger.error(f"Approve notify error: {e}")
        try:
            if is_photo:
                await query.edit_message_caption(caption=safe_text)
            else:
                await query.edit_message_text(safe_text)
        except Exception as e:
            logger.error(f"Edit message error: {e}")

    elif action == "reject":
        suffix = "\n\n❌ REJECTED"
        safe_text = original_text[: MAX_CAP - len(suffix)] + suffix
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"❌ আপনার অর্ডার Reject হয়েছে।\nযোগাযোগ করুন: {ADMIN_USERNAME}"
            )
        except Exception as e:
            logger.error(f"Reject notify error: {e}")
        try:
            if is_photo:
                await query.edit_message_caption(caption=safe_text)
            else:
                await query.edit_message_text(safe_text)
        except Exception as e:
            logger.error(f"Edit message error: {e}")


async def back_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Clear any active session when going back home
    store.pop(query.from_user.id, None)
    await query.edit_message_text(
        "🏠 Nolab Coin House\n\nনিচের বাটনে চাপুন:",
        reply_markup=home_keyboard()
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ বাতিল হয়েছে। /start দিন।")
    return ConversationHandler.END


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable not set!")
    if ADMIN_ID == 0:
        raise ValueError("ADMIN_ID environment variable not set!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(sell_start, pattern="^sell$")],
        states={
            SELECT_COIN: [
                CallbackQueryHandler(coin_selected, pattern="^coin_"),
            ],
            ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, amount_entered),
            ],
            ENTER_PROOF: [
                MessageHandler(filters.PHOTO, proof_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, proof_received),
            ],
            SELECT_PAYMENT: [
                CallbackQueryHandler(payment_selected, pattern="^pay_"),
            ],
            ENTER_PAYMENT_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, payment_details_entered),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            # BUGFIX: back_home inside conversation ends it cleanly
            CallbackQueryHandler(back_home, pattern="^back_home$"),
        ],
        # BUGFIX: allow_reentry lets users restart the flow without getting stuck
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))  # global — fires outside conv too
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(show_rates, pattern="^rates$"))
    app.add_handler(CallbackQueryHandler(back_home, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    # Periodic cleanup of abandoned sessions
    async def cleanup_sessions(ctx):
        now = time.time()
        expired = [uid for uid, data in list(store.items()) if now - data.get("_ts", now) > SESSION_TTL]
        for uid in expired:
            store.pop(uid, None)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired session(s)")
    app.job_queue.run_repeating(cleanup_sessions, interval=300, first=300)

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
