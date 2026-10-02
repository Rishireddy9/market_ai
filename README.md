# Indian Market Paper-Trading Prototype

This project is a **research and paper-trading prototype**, not a live trading
system or a promise of returns. Analysis uses Yahoo Finance historical bars,
which are not an execution-grade real-time feed. An explicit Upstox sandbox
adapter is available for testing order API payloads; no live API endpoint is
implemented.

The deterministic strategy checks a bullish EMA trend and an RSI range, proposes
a stop and a 3R reference level from ATR, and asks the risk module to size
whole-share cash-equity positions under configurable limits (defaults: 0.5%
per-trade risk, 2% daily loss, 5% drawdown, and minimum 2:1 reward/risk).
Historical backtests ratchet a long stop upward after price reaches 1R; the
stop trails the high-water mark by 2 ATR and never moves down. These defaults
are experimental parameters, not validated trading advice.

`--paper` records a risk-checked local proposal only; it does not simulate
market fills or monitor a position. `--backtest` simulates historical bars and
reports per-trade position/account return counts that reached 10% and 20%.
Those are historical outcomes, not a confidence estimate or prediction. This
prototype does not use an LLM to predict returns or decide trades; an LLM score
is not a calibrated probability. Options and index values cannot be traded by
the cash-equity strategy. Fees, slippage, liquidity, and taxes are not fully
modeled.

`--upstox-sandbox` explicitly submits a BUY market-order payload to Upstox's
fixed sandbox URL (`https://sandbox.upstox.com/v2/order/place`) after the local
risk check. It accepts NSE cash-equity `NSE_EQ|ISIN` instrument tokens only.
The exact token must correspond to the requested `.NS` symbol; the program
cannot verify that mapping. Sandbox submission sends only an entry order—it
does not attach or manage a stop/target order. Use this mode to test API
integration, not to validate live strategy performance. Upstox sandbox API
availability is phased; consult its [sandbox docs](https://upstox.com/developer/api-documentation/sandbox/)
to confirm current endpoint support. Sandbox tokens are separate from live
tokens and expire after 30 days per Upstox documentation.

## Setup and run

Use Python 3.10 or newer. In PowerShell, from the project folder:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --symbol "^NSEI"
.\.venv\Scripts\python.exe run.py --symbol RELIANCE.NS --paper
.\.venv\Scripts\python.exe run.py --symbol RELIANCE.NS --backtest
```

Without a mode flag, the program only analyzes and reports a candidate signal.
`--paper` stores a simulated, un-routed proposal in `paper_trades.sqlite3`;
`--backtest` runs the trailing-stop simulation on returned historical bars.
Yahoo Finance intraday history is limited and may be delayed; test results
depend on the symbol and period returned. `TRADING_CAPITAL`, `RISK_PER_TRADE`,
`MAX_DAILY_LOSS`, `MAX_ACCOUNT_DRAWDOWN`, `MAX_OPEN_POSITIONS`,
`MINIMUM_RISK_REWARD`, `TRAILING_ACTIVATION_R`, `TRAILING_ATR_MULTIPLE`, and
`TRADING_DATABASE_PATH` can override the defaults.

To explicitly test an Upstox sandbox order, first set the sandbox token only in
your local PowerShell session and confirm the instrument token from Upstox:

```powershell
$env:UPSTOX_SANDBOX_ACCESS_TOKEN = "<your sandbox token>"
.\.venv\Scripts\python.exe run.py --symbol RELIANCE.NS --upstox-sandbox --instrument-token "NSE_EQ|INE002A01018"
```

Replace the example ISIN with the instrument token for the symbol being
analyzed. Never use a live token, add credentials to source control, or send
secrets in chat. The sandbox flag is an explicit order-submission action; check
the printed result and Upstox sandbox order book. The program cannot guarantee
that the provider accepted or filled the simulated order beyond the API
response. Do not combine `--upstox-sandbox` with `--paper` or `--backtest`.

Run tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The optional FastAPI app is read-only:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

The optional LLM client is explanation-only. It requires
`LLM_API_KEY`, `LLM_API_ENDPOINT`, and `LLM_MODEL`; model output is not used to
create, size, or execute trades.

Before considering any live use, independently validate the strategy on reliable
broker data with realistic fees, slippage, survivorship/look-ahead controls,
walk-forward testing, and paper-forward testing. A broker-specific adapter,
exchange-compliant option contract selection, persistent account/risk state,
and independent operational controls would still need to be designed,
implemented, and reviewed. No trading system can guarantee a 10–20% return.
