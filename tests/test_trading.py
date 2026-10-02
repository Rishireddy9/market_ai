import math
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from agents.market_agent import MarketAgent, MarketState
from agents.portfolio_agent import PortfolioState
from agents.risk_agent import RiskAgent
from agents.strategy_agent import StrategyAgent, TradeSignal
from api.main import health
from backtester.engine import BacktestEngine
from backtester.metrics import calculate_metrics
from config.broker_config import BrokerConfig
from config.settings import Settings
from data.indicators import add_indicators
from data.market_data import MarketData
from data.option_chain import fetch_option_chain
from database.db import TradeDatabase
from execution.paper_executor import PaperExecutor
from llm.llm_client import LLMClient
from execution.trailing_stop import ratchet_trailing_stop
from execution.upstox_sandbox import (
    SANDBOX_ORDER_URL,
    UpstoxSandboxError,
    UpstoxSandboxExecutor,
)
from run import run_backtest, run_cycle


class TradingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configuration = Settings()
        self.signal = TradeSignal(
            symbol="RELIANCE.NS",
            direction="LONG",
            entry_price=100.0,
            stop_price=95.0,
            target_price=110.0,
            risk_reward_ratio=2.0,
            reason="test",
            timestamp="2026-01-01T10:00:00",
        )

    def test_indicators_produce_expected_columns_and_values(self) -> None:
        close = pd.Series([100 + index * 0.2 + math.sin(index) for index in range(80)])
        bars = pd.DataFrame(
            {
                "Open": close,
                "High": close + 1,
                "Low": close - 1,
                "Close": close,
                "Volume": 1000,
            }
        )

        enriched = add_indicators(bars)

        self.assertTrue({"ema20", "ema50", "rsi", "atr"}.issubset(enriched.columns))
        self.assertTrue(enriched.iloc[-1][["ema20", "ema50", "rsi", "atr"]].notna().all())
        self.assertGreater(enriched.iloc[-1]["atr"], 0)

    def test_market_agent_rejects_incomplete_indicator_history(self) -> None:
        frame = pd.DataFrame(
            [{"Close": 100, "ema20": 101, "ema50": 100, "rsi": 60, "atr": float("nan")}]
        )

        with self.assertRaisesRegex(ValueError, "incomplete"):
            MarketAgent().analyze(frame)

    def test_strategy_proposes_only_long_with_minimum_two_to_one_reward_risk(self) -> None:
        state = MarketState(100, "bullish", 60, 2, "2026-01-01T10:00:00")

        signal = StrategyAgent().generate(state, "RELIANCE.NS")

        self.assertIsNotNone(signal)
        self.assertEqual(signal.direction, "LONG")
        self.assertGreaterEqual(signal.risk_reward_ratio, 2)
        self.assertIsNone(StrategyAgent().generate(MarketState(100, "bearish", 60, 2, ""), "X"))
        self.assertIsNone(StrategyAgent().generate(MarketState(100, "bullish", 75, 2, ""), "X"))

    def test_risk_agent_sizes_position_by_stop_and_cash(self) -> None:
        decision = RiskAgent(self.configuration).validate_and_size(
            self.signal,
            equity=100_000,
        )

        self.assertTrue(decision.approved)
        self.assertEqual(decision.quantity, 100)
        self.assertEqual(decision.risk_amount, 500)

    def test_risk_agent_blocks_daily_loss_drawdown_positions_and_bad_reward_risk(self) -> None:
        agent = RiskAgent(self.configuration)
        self.assertFalse(agent.validate_and_size(self.signal, 100_000, daily_pnl=-2_000).approved)
        self.assertFalse(agent.validate_and_size(self.signal, 94_000, peak_equity=100_000).approved)
        self.assertFalse(agent.validate_and_size(self.signal, 100_000, open_positions=1).approved)
        bad_ratio = TradeSignal("X", "LONG", 100, 95, 109, 1.8, "test", "")
        self.assertFalse(agent.validate_and_size(bad_ratio, 100_000).approved)
        short = TradeSignal("X", "SHORT", 100, 105, 90, 2, "test", "")
        self.assertFalse(agent.validate_and_size(short, 100_000).approved)
        index = TradeSignal("^NSEI", "LONG", 100, 95, 110, 2, "test", "")
        self.assertFalse(agent.validate_and_size(index, 100_000).approved)

    def test_trailing_stop_only_moves_up_after_one_r_profit(self) -> None:
        kwargs = {
            "entry_price": 100.0,
            "initial_stop": 95.0,
            "current_stop": 95.0,
            "high_water_mark": 104.0,
            "current_atr": 2.0,
        }
        self.assertEqual(ratchet_trailing_stop(**kwargs), 95.0)

        first_ratchet = ratchet_trailing_stop(**{**kwargs, "high_water_mark": 110.0})
        self.assertEqual(first_ratchet, 106.0)
        tighter_stop = ratchet_trailing_stop(
            **{**kwargs, "current_stop": first_ratchet, "high_water_mark": 115.0}
        )
        self.assertEqual(tighter_stop, 111.0)
        self.assertEqual(
            ratchet_trailing_stop(
                **{**kwargs, "current_stop": tighter_stop, "high_water_mark": 112.0}
            ),
            tighter_stop,
        )

    def test_paper_executor_records_a_simulation_not_a_fill(self) -> None:
        with TemporaryDirectory() as directory:
            database = TradeDatabase(Path(directory) / "orders.sqlite3")
            result = PaperExecutor(database).execute(self.signal, 2)

            self.assertEqual(result["status"], "SIMULATED_NOT_ROUTED")
            self.assertIn("order_id", result)
            self.assertIn("no broker order", result["note"])

    def test_upstox_executor_targets_sandbox_and_sends_expected_order(self) -> None:
        response_body = json.dumps({"status": "success", "data": {"order_id": "sandbox-1"}})
        with patch(
            "execution.upstox_sandbox.urlopen",
            return_value=io.BytesIO(response_body.encode("utf-8")),
        ) as urlopen_mock:
            result = UpstoxSandboxExecutor("test-token").execute(
                self.signal,
                2,
                "NSE_EQ|INE002A01018",
            )

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.full_url, SANDBOX_ORDER_URL)
        self.assertIn("sandbox.upstox.com", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["instrument_token"], "NSE_EQ|INE002A01018")
        self.assertEqual(payload["quantity"], 2)
        self.assertEqual(payload["transaction_type"], "BUY")
        self.assertEqual(result["status"], "SANDBOX_SUBMITTED")
        self.assertIn("No stop/target order", result["note"])

    def test_upstox_executor_refuses_missing_token_and_non_equity_instruments(self) -> None:
        with self.assertRaisesRegex(UpstoxSandboxError, "UPSTOX_SANDBOX_ACCESS_TOKEN"):
            UpstoxSandboxExecutor("").execute(self.signal, 1, "NSE_EQ|INE002A01018")
        with self.assertRaisesRegex(UpstoxSandboxError, "cash-equity tokens"):
            UpstoxSandboxExecutor("test-token").execute(self.signal, 1, "NSE_INDEX|Nifty 50")

    def test_metrics_are_computed_from_trade_results(self) -> None:
        metrics = calculate_metrics(
            [{"pnl": 100.0}, {"pnl": -50.0}],
            initial_capital=1_000,
        )

        self.assertEqual(metrics["trade_count"], 2)
        self.assertEqual(metrics["win_rate_pct"], 50)
        self.assertEqual(metrics["profit_factor"], 2)
        self.assertEqual(metrics["net_pnl"], 50)
        self.assertEqual(metrics["account_return_pct"], 5)
        self.assertAlmostEqual(metrics["max_drawdown_pct"], 50 / 1_100 * 100)

    def test_market_data_normalizes_multi_index_columns(self) -> None:
        columns = pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Volume"], ["^NSEI"]]
        )
        bars = pd.DataFrame([[100, 102, 99, 101, 1000]], columns=columns)
        with patch("data.market_data.yf.download", return_value=bars):
            result = MarketData().get_history("^NSEI")

        self.assertTrue({"Open", "High", "Low", "Close", "Volume"}.issubset(result.columns))
        self.assertEqual(float(result["Close"].iloc[0]), 101)

    def test_portfolio_starts_at_configured_equity_and_tracks_peak(self) -> None:
        portfolio = PortfolioState(10_000)
        portfolio.record_realized_pnl(500)

        self.assertEqual(portfolio.equity, 10_500)
        self.assertEqual(portfolio.peak_equity, 10_500)

    def test_backtester_runs_on_historical_ohlc_bars(self) -> None:
        close = pd.Series(
            [100 + index * 0.15 + math.sin(index * 0.75) for index in range(100)]
        )
        bars = pd.DataFrame(
            {
                "Open": close.to_numpy(),
                "High": close.to_numpy() + 0.8,
                "Low": close.to_numpy() - 0.8,
                "Close": close.to_numpy(),
                "Volume": 1000,
            },
            index=pd.date_range("2026-01-01", periods=100, freq="5min"),
        )

        result = BacktestEngine(self.configuration).run(bars, "RELIANCE.NS")

        self.assertIn("trades", result)
        self.assertEqual(result["metrics"]["trade_count"], len(result["trades"]))

    def test_backtest_reports_position_and_account_target_counts(self) -> None:
        result = calculate_metrics(
            [
                {"pnl": 12_000, "position_return_pct": 12, "account_return_pct": 12},
                {"pnl": -2_000, "position_return_pct": -2, "account_return_pct": -2},
            ],
            initial_capital=100_000,
        )

        self.assertEqual(result["trades_position_return_at_least_10pct"], 1)
        self.assertEqual(result["trades_position_return_at_least_20pct"], 0)
        self.assertEqual(result["trades_account_return_at_least_10pct"], 1)
        self.assertEqual(result["trades_account_return_at_least_20pct"], 0)

    def test_live_and_options_paths_fail_closed_without_providers(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "not implemented"):
            BrokerConfig(None, None, None, False).require_live_broker()
        with self.assertRaisesRegex(RuntimeError, "Options trading is disabled"):
            fetch_option_chain(None, "^NSEI")

    def test_llm_is_optional_and_requires_explicit_configuration(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            client = LLMClient(api_key="", endpoint="", model="")
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            client.explain(MarketState(100, "neutral", 50, 1, ""))

    def test_run_cycle_persists_only_a_risk_approved_paper_order(self) -> None:
        state = MarketState(100, "bullish", 60, 2, "2026-01-01T10:00:00")
        with TemporaryDirectory() as directory:
            configuration = Settings(database_path=str(Path(directory) / "orders.sqlite3"))
            with (
                patch("run.MarketData.get_history", return_value=pd.DataFrame()),
                patch("run.add_indicators", return_value=pd.DataFrame()),
                patch("run.MarketAgent.analyze", return_value=state),
                patch("run.StrategyAgent.generate", return_value=self.signal),
                patch("run.settings", configuration),
            ):
                result = run_cycle("RELIANCE.NS", place_paper_order=True)

            self.assertEqual(result["status"], "SIMULATED_NOT_ROUTED")
            self.assertEqual(result["result"]["order"]["quantity"], 100)
            self.assertTrue(Path(configuration.database_path).exists())

    def test_run_cycle_can_explicitly_submit_to_upstox_sandbox(self) -> None:
        state = MarketState(100, "bullish", 60, 2, "2026-01-01T10:00:00")
        with TemporaryDirectory() as directory:
            configuration = Settings(database_path=str(Path(directory) / "orders.sqlite3"))
            sandbox_response = {
                "status": "SANDBOX_SUBMITTED",
                "response": {"status": "success"},
            }
            with (
                patch("run.MarketData.get_history", return_value=pd.DataFrame()),
                patch("run.add_indicators", return_value=pd.DataFrame()),
                patch("run.MarketAgent.analyze", return_value=state),
                patch("run.StrategyAgent.generate", return_value=self.signal),
                patch("run.settings", configuration),
                patch(
                    "run.UpstoxSandboxExecutor.execute",
                    return_value=sandbox_response,
                ) as execute_mock,
            ):
                result = run_cycle(
                    "RELIANCE.NS",
                    upstox_sandbox=True,
                    instrument_token="NSE_EQ|INE002A01018",
                )

            self.assertEqual(result["status"], "SANDBOX_SUBMITTED")
            execute_mock.assert_called_once()
            self.assertTrue(Path(configuration.database_path).exists())

    def test_health_endpoint_reports_paper_only_mode(self) -> None:
        self.assertEqual(health(), {"status": "ok", "execution": "paper-only"})

    def test_backtest_command_path_uses_backtester(self) -> None:
        with patch("run.MarketData.get_history", return_value=pd.DataFrame({"Close": [1]})):
            with patch(
                "run.BacktestEngine.run",
                return_value={"trades": [], "metrics": {"trade_count": 0}},
            ):
                result = run_backtest("RELIANCE.NS")

        self.assertEqual(result["status"], "HISTORICAL_BACKTEST")
        self.assertEqual(result["symbol"], "RELIANCE.NS")


if __name__ == "__main__":
    unittest.main()
