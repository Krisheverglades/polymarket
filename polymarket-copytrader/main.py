"""
main.py — entrypoint. Wires everything together and runs the polling loop.

Run with: python main.py
For always-on operation, use the included systemd service file
(polymarket-copytrader.service) rather than running this in a bare
terminal / tmux session.
"""
import asyncio
import logging
import sys

from config import CFG, validate_config
from wallet_tracker import WalletTracker
from risk_manager import RiskManager
from clob_execution import ClobExecutor
from copy_trader import CopyTrader
from telegram_bot import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("main")


async def main():
    validate_config()

    bot_state = {"paused": False}
    risk = RiskManager()
    tracker = WalletTracker(CFG.tracked_wallets)
    executor = ClobExecutor()
    notifier = TelegramNotifier(risk, bot_state)
    trader = CopyTrader(executor, risk, notifier, bot_state)

    await notifier.start_polling()
    await notifier.send(
        f"🤖 Copy trader starting.\n"
        f"Tracking {len(CFG.tracked_wallets)} wallets.\n"
        f"Max position: ${CFG.max_position_size_usdc}\n"
        f"Max daily loss: ${CFG.max_daily_loss_usdc}"
    )

    await tracker.prime()
    log.info("Entering main loop.")

    try:
        while True:
            if risk.kill_switch_active():
                log.critical("Kill switch active — halting main loop.")
                await notifier.send("🛑 Kill switch active. Bot stopped. Delete the KILL file and restart to resume.")
                break

            try:
                new_trades = await tracker.poll_new_trades()
                for trade in new_trades:
                    log.info(f"New trade detected from {trade.get('_source_wallet')}: {trade}")
                    await trader.handle_trade(trade)
            except Exception as e:
                log.error(f"Error in polling loop: {e}", exc_info=True)
                await notifier.send(f"⚠️ Polling loop error: {e}")

            await asyncio.sleep(CFG.poll_interval_seconds)
    finally:
        await tracker.close()
        await notifier.stop()


if __name__ == "__main__":
    asyncio.run(main())
