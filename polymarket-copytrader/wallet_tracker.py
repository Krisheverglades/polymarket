"""
wallet_tracker.py — monitors the TRACKED_WALLETS list, keeps a record of
the last trade seen per wallet, and surfaces newly-detected trades for
the copy trader to act on. Also computes basic quality stats used to
periodically sanity-check whether a wallet is still worth following.
"""
import asyncio
import logging
from datetime import datetime, timezone
from data_api import DataAPI

log = logging.getLogger("wallet_tracker")


class WalletTracker:
    def __init__(self, wallets: list[str]):
        self.wallets = wallets
        self.api = DataAPI()
        # last trade id/timestamp seen per wallet, so we only act on NEW trades
        self._last_seen: dict[str, str] = {}

    async def prime(self):
        """
        Call once at startup. Records the most recent trade per wallet as
        the baseline so we don't immediately try to copy someone's entire
        trade history the moment the bot starts.
        """
        for w in self.wallets:
            trades = await self.api.get_trades(w, limit=1)
            if trades:
                self._last_seen[w] = trades[0].get("transactionHash") or trades[0].get("id")
            else:
                self._last_seen[w] = None
        log.info(f"Primed {len(self.wallets)} wallets.")

    async def poll_new_trades(self) -> list[dict]:
        """
        Check every tracked wallet for trades newer than what we've seen.
        Returns a flat list of new trade dicts, each tagged with the
        source wallet address.
        """
        new_trades = []
        for w in self.wallets:
            try:
                trades = await self.api.get_trades(w, limit=10)
            except Exception as e:
                log.warning(f"Failed to fetch trades for {w}: {e}")
                continue

            if not trades:
                continue

            last_seen_id = self._last_seen.get(w)
            fresh = []
            for t in trades:
                tid = t.get("transactionHash") or t.get("id")
                if tid == last_seen_id:
                    break
                fresh.append(t)

            if fresh:
                self._last_seen[w] = fresh[0].get("transactionHash") or fresh[0].get("id")
                for t in reversed(fresh):  # oldest first, preserve order
                    t["_source_wallet"] = w
                    new_trades.append(t)

        return new_trades

    async def wallet_summary(self, wallet: str) -> dict:
        """Quick health-check snapshot for a wallet — used for periodic review."""
        positions = await self.api.get_positions(wallet)
        value = await self.api.get_value(wallet)
        open_count = len(positions)
        total_pnl = sum(float(p.get("cashPnl", 0) or 0) for p in positions)
        return {
            "wallet": wallet,
            "open_positions": open_count,
            "unrealized_pnl_usdc": round(total_pnl, 2),
            "portfolio_value_usdc": value.get("value") if isinstance(value, dict) else None,
        }

    async def close(self):
        await self.api.close()
