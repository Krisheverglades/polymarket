"""
config.py — All runtime configuration lives here, pulled from environment
variables. Nothing sensitive is hardcoded. Copy .env.example to .env and
fill it in before running anything.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _list(name: str) -> list[str]:
    val = os.getenv(name, "")
    return [x.strip() for x in val.split(",") if x.strip()]


@dataclass
class Config:
    # --- Wallet / execution credentials ---
    # PRIVATE_KEY should belong to a wallet that holds ONLY the capital
    # you're willing to trade with. Do not reuse a wallet that holds
    # savings, NFTs, or anything else.
    private_key: str = os.getenv("PK", "")
    funder_address: str = os.getenv("FUNDER_ADDRESS", "")  # Polymarket proxy wallet
    signature_type: int = _int("SIGNATURE_TYPE", 1)  # 1 = email/Magic, 2 = MetaMask/EOA

    # --- API endpoints ---
    clob_host: str = "https://clob.polymarket.com"
    data_api_host: str = "https://data-api.polymarket.com"
    gamma_api_host: str = "https://gamma-api.polymarket.com"
    chain_id: int = 137  # Polygon mainnet

    # --- Telegram ---
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Wallets being copy-traded ---
    tracked_wallets: list[str] = field(default_factory=lambda: _list("TRACKED_WALLETS"))

    # --- Risk controls (all hard limits, checked before every order) ---
    max_position_size_usdc: float = _float("MAX_POSITION_SIZE_USDC", 25.0)
    max_daily_loss_usdc: float = _float("MAX_DAILY_LOSS_USDC", 100.0)
    max_open_positions: int = _int("MAX_OPEN_POSITIONS", 5)
    max_total_exposure_usdc: float = _float("MAX_TOTAL_EXPOSURE_USDC", 300.0)
    copy_size_fraction: float = _float("COPY_SIZE_FRACTION", 0.05)  # copy at 5% of source wallet's size
    min_source_wallet_trade_usdc: float = _float("MIN_SOURCE_TRADE_USDC", 50.0)  # ignore dust trades
    max_slippage_pct: float = _float("MAX_SLIPPAGE_PCT", 3.0)

    # --- Polling ---
    poll_interval_seconds: int = _int("POLL_INTERVAL_SECONDS", 15)

    # --- Kill switch ---
    # If a file named KILL exists in the project root, the bot halts all
    # trading immediately on next loop iteration. Simplest possible
    # emergency stop — touch KILL from SSH or via the Telegram /kill command.
    kill_file: str = "KILL"


CFG = Config()


def validate_config():
    errors = []
    if not CFG.private_key:
        errors.append("PK (private key) not set")
    if not CFG.telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN not set")
    if not CFG.telegram_chat_id:
        errors.append("TELEGRAM_CHAT_ID not set")
    if not CFG.tracked_wallets:
        errors.append("TRACKED_WALLETS not set (comma-separated addresses)")
    if errors:
        raise SystemExit("Config errors:\n  - " + "\n  - ".join(errors))
