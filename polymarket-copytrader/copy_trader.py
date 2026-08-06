"""
copy_trader.py — glues wallet_tracker (what did they do), risk_manager
(are we allowed to react), and clob_execution (place the order) together.

Copy sizing is proportional: COPY_SIZE_FRACTION of the source wallet's
trade notional, capped by MAX_POSITION_SIZE_USDC. A whale buying $10k of
something at 5% copy fraction is a $500 order for you, capped down to
your MAX_POSITION_SIZE_USDC if that's smaller — never scaled up.
"""
import logging
from config import CFG

log = logging.getLogger("copy_trader")


class CopyTrader:
    def __init__(self, executor, risk_manager, notifier, bot_state):
        self.executor = executor
        self.risk = risk_manager
        self.notifier = notifier
        self.bot_state = bot_state

    def _proposed_size(self, source_trade: dict) -> float:
        source_size = float(source_trade.get("size", 0))
        source_price = float(source_trade.get("price", 0))
        source_notional = source_size * source_price
        proposed = source_notional * CFG.copy_size_fraction
        return min(proposed, CFG.max_position_size_usdc)

    async def handle_trade(self, trade: dict):
        source_wallet = trade.get("_source_wallet")
        side = (trade.get("side") or "").upper()
        token_id = trade.get("asset") or trade.get("token_id")
        source_size = float(trade.get("size", 0))
        source_price = float(trade.get("price", 0))
        source_notional = source_size * source_price

        if source_notional < CFG.min_source_wallet_trade_usdc:
            log.info(f"Ignoring dust trade from {source_wallet}: ${source_notional:.2f}")
            return

        if self.bot_state.get("paused"):
            log.info("Bot is paused — skipping copy trade.")
            return

        if side != "BUY":
            # SELL-copying (mirroring exits) is intentionally not wired up
            # by default — see README "Extending" section. Log and skip
            # for now rather than guessing at position-matching logic.
            log.info(f"Non-BUY trade from {source_wallet} ignored (side={side}).")
            return

        proposed = self._proposed_size(trade)
        approved, reason = self.risk.approve_order(proposed)

        if not approved:
            log.warning(f"Trade REJECTED by risk manager: {reason}")
            await self.notifier.send(
                f"⛔ Skipped copy trade\n"
                f"Source: {source_wallet[:10]}...\n"
                f"Reason: {reason}"
            )
            return

        try:
            resp = self.executor.place_market_buy(
                token_id=token_id,
                size_usdc=proposed,
                max_slippage_pct=CFG.max_slippage_pct,
            )
            self.risk.record_fill(notional_usdc=proposed)
            self.risk.state.open_positions_count += 1
            await self.notifier.send(
                f"✅ Copied trade\n"
                f"Source: {source_wallet[:10]}...\n"
                f"Size: ${proposed:.2f}\n"
                f"Token: {token_id}\n"
                f"Order: {resp.get('orderID', resp)}"
            )
        except Exception as e:
            log.error(f"Order placement failed: {e}")
            await self.notifier.send(f"⚠️ Order FAILED for trade from {source_wallet[:10]}...: {e}")
