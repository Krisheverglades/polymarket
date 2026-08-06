# Polymarket Copy Trading Bot

Monitors a list of wallets on Polymarket, mirrors their BUY trades
proportionally, and executes automatically via the CLOB API. Sends
alerts and accepts control commands via Telegram.

**This is a starting scaffold, not a finished, battle-tested product.**
Read the whole README before funding a wallet.

## Architecture

```
wallet_tracker.py   — polls Data API for new trades from tracked wallets
risk_manager.py     — hard limits checked before every order (READ THIS FILE)
copy_trader.py       — sizing logic, glues tracker → risk → execution
clob_execution.py   — places orders via py-clob-client-v2
telegram_bot.py     — alerts + /status /pause /resume /kill commands
config.py            — all settings, pulled from .env
main.py               — polling loop
```

## Setup

1. **Create a dedicated trading wallet.** Do not use a wallet that holds
   savings, other tokens, or NFTs. Fund it with only the amount you're
   willing to lose entirely — because with automated execution, that's
   a real possibility, not a disclaimer formality.

2. Copy `.env.example` to `.env` and fill it in:
   ```
   cp .env.example .env
   ```
   - `PK`: private key of your dedicated trading wallet
   - `TRACKED_WALLETS`: addresses you want to copy (comma-separated)
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: from @BotFather and @userinfobot

3. Install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Set token allowances first.** Before the CLOB will accept your
   orders, your wallet needs to approve the exchange contracts to spend
   your USDC. See Polymarket's docs:
   https://docs.polymarket.com — "Token Allowances" section. Do this
   once, manually, before running the bot.

5. Dry-run locally first:
   ```
   python main.py
   ```
   Watch the logs (`logs/bot.log`) and Telegram alerts for a day with
   `MAX_POSITION_SIZE_USDC` set very low (e.g. $1-2) before trusting it
   with real size.

## Deploying to a VPS (always-on)

```bash
# On the VPS:
sudo useradd -r -s /bin/false copytrader
sudo mkdir -p /opt/polymarket-copytrader
sudo chown copytrader:copytrader /opt/polymarket-copytrader
# copy project files there, set up venv, install deps as above

sudo cp polymarket-copytrader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now polymarket-copytrader
sudo journalctl -u polymarket-copytrader -f   # watch logs
```

**VPS security basics that matter here specifically:**
- Put `.env` at 600 permissions (`chmod 600 .env`), owned by the
  `copytrader` user only.
- Use SSH key auth only, disable password login, keep the box patched.
- Consider a secrets manager (e.g. environment injection via systemd
  `EnvironmentFile`, or a vault) instead of a plaintext `.env` for
  anything beyond initial testing.
- A VPS with your private key on it is a target. Treat it like it holds
  cash, because it does.

## Risk controls (in `risk_manager.py` / `.env`)

| Control | Purpose |
|---|---|
| `MAX_POSITION_SIZE_USDC` | Hard cap per individual copy trade |
| `MAX_DAILY_LOSS_USDC` | Bot halts itself for the day once hit |
| `MAX_OPEN_POSITIONS` | Caps concurrent bets |
| `MAX_TOTAL_EXPOSURE_USDC` | Caps total capital at risk at once |
| `COPY_SIZE_FRACTION` | Scales your size relative to the source wallet's size (never up, only down) |
| `KILL` file / `/kill` Telegram command | Immediate hard stop |

Start every one of these conservative. It's much easier to raise a
limit after a week of good behavior than to explain to yourself why it
was set too high on day one.

## What this scaffold does NOT do (be aware)

- **No exit/sell mirroring.** It copies BUYs only. Selling is left to
  you (or you can extend `copy_trader.py` — the hook is there and
  commented). This is deliberate: matching your position to their exit
  correctly requires more state tracking than a first pass should
  guess at.
- **No real win-rate calculation.** `data_api.py` has a placeholder —
  computing true win rate requires joining trade history against
  market resolution outcomes via the Gamma API, which isn't wired up
  yet.
- **No backtesting.** You are running this against live markets with
  live money from day one unless you test with tiny position sizes
  first. Do that.
- **No protection against the source wallet being wrong, manipulative,
  or itself a bot with different risk tolerance than you.** "Wallet has
  a good win rate over N trades" is not the same as "wallet has an
  edge" — small samples, variance, and market impact all cut against
  naive copy-trading. Treat the tracked-wallet list as a hypothesis to
  monitor, not a certainty.

## A blunt note

Automated trading with real capital is genuinely risky, independent of
whether the code is correct. Bugs happen. APIs change. Liquidity dries
up. The wallets you're copying can start losing right after you start
copying them (this is common — you're often seeing survivorship in a
snapshot, not a guaranteed forward edge). Keep position sizes small
relative to what you can afford to lose while you build confidence in
the system, and don't treat a good week as proof it works.
