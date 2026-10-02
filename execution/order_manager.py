"""Risk-gated orchestration for simulated orders only."""

from dataclasses import asdict
from typing import Any

from agents.risk_agent import RiskAgent
from agents.strategy_agent import TradeSignal
from execution.paper_executor import PaperExecutor


class OrderManager:
    def __init__(self, risk_agent: RiskAgent, paper_executor: PaperExecutor) -> None:
        self.risk_agent = risk_agent
        self.paper_executor = paper_executor

    def submit_paper_order(
        self,
        signal: TradeSignal,
        equity: float,
        daily_pnl: float = 0.0,
        open_positions: int = 0,
        peak_equity: float | None = None,
    ) -> dict[str, Any]:
        decision = self.risk_agent.validate_and_size(
            signal,
            equity=equity,
            daily_pnl=daily_pnl,
            open_positions=open_positions,
            peak_equity=peak_equity,
        )
        if not decision.approved:
            return {"status": "REJECTED", "reason": decision.reason}
        return {
            "status": "SIMULATED_NOT_ROUTED",
            "risk": asdict(decision),
            "order": self.paper_executor.execute(signal, decision.quantity),
        }
