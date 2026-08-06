"""
telegram_bot.py — sends trade alerts and exposes a few control commands
so you can monitor and stop the bot from your phone.

Commands:
  /status  — current risk state, open positions, daily P&L
  /pause   — soft-pause: stop opening new copy trades (existing positions untouched)
  /resume  — resume after a pause
  /kill    — hard stop: creates the KILL file, halts everything immediately
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import CFG

log = logging.getLogger("telegram_bot")


class TelegramNotifier:
    def __init__(self, risk_manager, bot_state):
        self.risk_manager = risk_manager
        self.bot_state = bot_state  # shared dict, e.g. {"paused": False}
        self.app = Application.builder().token(CFG.telegram_bot_token).build()
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("pause", self.cmd_pause))
        self.app.add_handler(CommandHandler("resume", self.cmd_resume))
        self.app.add_handler(CommandHandler("kill", self.cmd_kill))

    async def send(self, text: str):
        try:
            await self.app.bot.send_message(chat_id=CFG.telegram_chat_id, text=text)
        except Exception as e:
            log.warning(f"Telegram send failed: {e}")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        s = self.risk_manager.status()
        paused = self.bot_state.get("paused", False)
        msg = (
            f"Paused: {paused}\n"
            f"Halted: {s['halted']} ({s['halt_reason']})\n"
            f"Daily P&L: ${s['daily_pnl_usdc']}\n"
            f"Open positions: {s['open_positions']}\n"
            f"Total exposure: ${s['total_exposure_usdc']}"
        )
        await update.message.reply_text(msg)

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.bot_state["paused"] = True
        await update.message.reply_text("Paused. Existing positions are untouched; no new copy trades will open.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.bot_state["paused"] = False
        await update.message.reply_text("Resumed.")

    async def cmd_kill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        open(CFG.kill_file, "w").close()
        self.risk_manager.halt("Kill switch triggered via Telegram")
        await update.message.reply_text("KILL SWITCH ACTIVATED. All new trading halted. Delete the KILL file to resume.")

    async def start_polling(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def stop(self):
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
