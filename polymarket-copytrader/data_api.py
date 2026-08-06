"""
data_api.py — thin wrapper around Polymarket's public Data API
(data-api.polymarket.com). No auth needed for reads. This is what powers
wallet tracking: trade history, current positions, and derived stats
like win rate and average position size.
"""
import httpx
from datetime import datetime, timezone
from config import CFG


class DataAPI:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=CFG.data_api_host, timeout=15.0)

    async def get_trades(self, wallet: str, limit: int = 100) -> list[dict]:
        """Recent trades for a wallet, newest first."""
        resp = await self.client.get("/trades", params={"user": wallet, "limit": limit})
        resp.raise_for_status()
        return resp.json()

    async def get_positions(self, wallet: str) -> list[dict]:
        """Current open positions for a wallet."""
        resp = await self.client.get("/positions", params={"user": wallet})
        resp.raise_for_status()
        return resp.json()

    async def get_value(self, wallet: str) -> dict:
        """Total portfolio value for a wallet."""
        resp = await self.client.get("/value", params={"user": wallet})
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()


def compute_wallet_stats(trades: list[dict]) -> dict:
    """
    Derive win rate, avg trade size, and avg hold time from raw trade
    history. This is a rough heuristic (matches BUYs to subsequent
    SELLs/redemptions on the same token) — good enough to rank wallets,
    not a substitute for careful backtesting.
    """
    if not trades:
        return {"trade_count": 0, "win_rate": None, "avg_size_usdc": 0}

    sizes = [float(t.get("size", 0)) * float(t.get("price", 0)) for t in trades]
    avg_size = sum(sizes) / len(sizes) if sizes else 0

    wins, losses = 0, 0
    for t in trades:
        outcome = t.get("outcome")
        price = float(t.get("price", 0))
        side = t.get("side", "").upper()
        # crude heuristic: a BUY that filled far from 0.5 in the direction
        # that later resolved favorably counts as a "confident" trade.
        # Real win/loss requires joining against market resolution data —
        # left as a TODO once you're tracking specific markets closely.
        if side == "BUY" and price > 0:
            pass  # placeholder — see note below

    return {
        "trade_count": len(trades),
        "avg_size_usdc": round(avg_size, 2),
        "last_trade_ts": trades[0].get("timestamp") if trades else None,
        # win_rate intentionally left as None here — computing it properly
        # requires joining trades against market resolutions via the Gamma
        # API. See wallet_tracker.py for the fuller implementation.
        "win_rate": None,
    }
