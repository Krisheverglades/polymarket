"""
risk_manager.py — every automated order passes through here first.
This is the most important file in the project. If in doubt, this module
should say no. A blocked trade costs you a missed opportunity; a bug that
bypasses risk checks can cost you your whole balance.
"""
import logging
import os
from datetime import datetime, timezone, date
from dataclasses import dataclass, field
from config import CFG

log = logging.getLogger("risk_manager")


@dataclass
class RiskState:
    daily_pnl_usdc: float = 0.0
    daily_pnl_date: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    open_positions_count: int = 0
    total_exposure_usdc: float = 0.0
    halted: bool = False
    halt_reason: str = ""


class RiskManager:
    def __init__(self):
        self.state = RiskState()

    def _reset_daily_if_needed(self):
        today = datetime.now(timezone.utc).date()
        if today != self.state.daily_pnl_date:
            log.info(f"New UTC day — resetting daily P&L counter (was {self.state.daily_pnl_usdc:.2f})")
            self.state.daily_pnl_usdc = 0.0
            self.state.daily_pnl_date = today

    def kill_switch_active(self) -> bool:
        return os.path.exists(CFG.kill_file) or self.state.halted

    def halt(self, reason: str):
        self.state.halted = True
        self.state.halt_reason = reason
        log.critical(f"TRADING HALTED: {reason}")

    def record_fill(self, notional_usdc: float, realized_pnl_usdc: float = 0.0):
        self._reset_daily_if_needed()
        self.state.daily_pnl_usdc += realized_pnl_usdc
        self.state.total_exposure_usdc += notional_usdc

    def record_close(self, notional_usdc: float):
        self.state.total_exposure_usdc = max(0.0, self.state.total_exposure_usdc - notional_usdc)
        self.state.open_positions_count = max(0, self.state.open_positions_count - 1)

    def approve_order(self, proposed_size_usdc: float) -> tuple[bool, str]:
        """
        Returns (approved: bool, reason: str). Every check here is a hard
        stop — no overrides, no "just this once." Tune the numbers in
        config/.env, not by bypassing this function.
        """
        self._reset_daily_if_needed()

        if self.kill_switch_active():
            return False, f"Kill switch active ({self.state.halt_reason or 'KILL file present'})"

        if proposed_size_usdc <= 0:
            return False, "Non-positive order size"

        if proposed_size_usdc > CFG.max_position_size_usdc:
            return False, (
                f"Order ${proposed_size_usdc:.2f} exceeds max position size "
                f"${CFG.max_position_size_usdc:.2f}"
            )

        if self.state.daily_pnl_usdc <= -abs(CFG.max_daily_loss_usdc):
            self.halt(f"Daily loss limit hit: ${self.state.daily_pnl_usdc:.2f}")
            return False, self.state.halt_reason

        if self.state.open_positions_count >= CFG.max_open_positions:
            return False, f"Max open positions reached ({CFG.max_open_positions})"

        if self.state.total_exposure_usdc + proposed_size_usdc > CFG.max_total_exposure_usdc:
            return False, (
                f"Would exceed max total exposure "
                f"(${self.state.total_exposure_usdc:.2f} + ${proposed_size_usdc:.2f} "
                f"> ${CFG.max_total_exposure_usdc:.2f})"
            )

        return True, "OK"

    def status(self) -> dict:
        return {
            "halted": self.state.halted,
            "halt_reason": self.state.halt_reason,
            "daily_pnl_usdc": round(self.state.daily_pnl_usdc, 2),
            "open_positions": self.state.open_positions_count,
            "total_exposure_usdc": round(self.state.total_exposure_usdc, 2),
        }
