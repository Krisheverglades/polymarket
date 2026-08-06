"""
clob_execution.py — wraps py-clob-client-v2 for placing orders on
Polymarket's CLOB. Kept separate from copy_trader.py so the actual
"sign and send a transaction" surface area is small and easy to audit.
"""
import logging
from config import CFG

log = logging.getLogger("clob_execution")


class ClobExecutor:
    def __init__(self):
        # Imported lazily so the rest of the codebase (wallet tracking,
        # risk logic) can be tested/run without needing a funded wallet
        # or the clob client installed.
        from py_clob_client_v2 import ClobClient

        self.client = ClobClient(
            host=CFG.clob_host,
            chain_id=CFG.chain_id,
            key=CFG.private_key,
        )
        self._creds = self.client.create_or_derive_api_key()
        self.client = ClobClient(
            host=CFG.clob_host,
            chain_id=CFG.chain_id,
            key=CFG.private_key,
            creds=self._creds,
        )

    def get_market(self, token_id: str) -> dict:
        """Fetch current order book / price for a token id."""
        return self.client.get_order_book(token_id)

    def best_ask(self, token_id: str) -> float | None:
        book = self.get_market(token_id)
        asks = book.get("asks") if isinstance(book, dict) else None
        if not asks:
            return None
        return float(min(a["price"] for a in asks))

    def place_market_buy(self, token_id: str, size_usdc: float, max_slippage_pct: float) -> dict:
        """
        Places a marketable limit buy: fetches best ask, adds slippage
        tolerance, converts USDC notional to token size, and submits.
        Returns the raw order response.
        """
        from py_clob_client_v2 import OrderArgs, Side, PartialCreateOrderOptions

        ask = self.best_ask(token_id)
        if ask is None:
            raise RuntimeError(f"No liquidity / order book for token {token_id}")

        limit_price = round(min(ask * (1 + max_slippage_pct / 100), 0.999), 3)
        size_tokens = round(size_usdc / limit_price, 2)

        log.info(
            f"Placing BUY: token={token_id} price={limit_price} "
            f"size={size_tokens} (~${size_usdc:.2f})"
        )

        order = OrderArgs(
            token_id=token_id,
            price=limit_price,
            side=Side.BUY,
            size=size_tokens,
        )
        resp = self.client.create_and_post_order(
            order_args=order,
            options=PartialCreateOrderOptions(tick_size="0.01"),
        )
        return resp

    def place_market_sell(self, token_id: str, size_tokens: float, max_slippage_pct: float) -> dict:
        from py_clob_client_v2 import OrderArgs, Side, PartialCreateOrderOptions

        book = self.get_market(token_id)
        bids = book.get("bids") if isinstance(book, dict) else None
        if not bids:
            raise RuntimeError(f"No liquidity / order book for token {token_id}")
        best_bid = float(max(b["price"] for b in bids))
        limit_price = round(max(best_bid * (1 - max_slippage_pct / 100), 0.001), 3)

        log.info(f"Placing SELL: token={token_id} price={limit_price} size={size_tokens}")

        order = OrderArgs(
            token_id=token_id,
            price=limit_price,
            side=Side.SELL,
            size=size_tokens,
        )
        resp = self.client.create_and_post_order(
            order_args=order,
            options=PartialCreateOrderOptions(tick_size="0.01"),
        )
        return resp
