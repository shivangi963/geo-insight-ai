"""The AI assistant, with Gemini replaced by a fake extractor.

Regression: the investment path used to crash with a TypeError because options were
passed as one dict instead of keyword arguments.
"""

import asyncio
import inspect

import pytest

from backend.app.agents import local_expert as le
from backend.app.agents.local_expert import LocalExpertAgent

EMPTY = {
    "price": None, "rent": None, "down_pct": None, "expense_ratio": None,
    "interest_rate": None, "loan_term": None, "holding_years": None,
    "appreciation_rate": None, "annual_emi": None, "is_investment_query": False,
}


def agent_with_extraction(monkeypatch, **extracted):
    async def fake_extract(self, query):
        return {**EMPTY, **extracted}

    monkeypatch.setattr(LocalExpertAgent, "_extract_with_gemini", fake_extract)
    return LocalExpertAgent()


def ask(agent, query):
    return asyncio.run(agent.process_query(query))


def test_investment_query_runs_the_full_analysis(monkeypatch):
    agent = agent_with_extraction(monkeypatch, price=8_000_000, rent=25_000, is_investment_query=True)
    result = ask(agent, "Analyse investment: property Rs. 80L, rent Rs. 25,000/month")

    assert result["success"] is True
    assert result["type"] == "investment_analysis"
    assert result["calculations"]["gross_yield"] == pytest.approx(3.75)


def test_custom_options_reach_the_calculator(monkeypatch):
    agent = agent_with_extraction(
        monkeypatch, price=12_000_000, rent=40_000, down_pct=20.0, interest_rate=9.0,
        is_investment_query=True,
    )
    result = ask(agent, "ROI for 1.2 Cr flat with 40,000 monthly rent, 20% down, 9% interest")

    assert result["type"] == "investment_analysis"
    loan = 12_000_000 * 0.8
    expected_emi = le._monthly_mortgage(loan, 9.0, 20)
    assert result["calculations"]["monthly_emi"] == pytest.approx(expected_emi, rel=1e-6)


def test_no_extracted_numbers_gives_the_help_message(monkeypatch):
    agent = agent_with_extraction(monkeypatch)
    result = ask(agent, "hello")
    assert result["type"] == "general"


def test_assistant_degrades_to_help_when_gemini_is_unavailable():
    agent = LocalExpertAgent()
    agent.use_gemini = False  # no key, quota exhausted, SDK missing...
    result = ask(agent, "Analyse investment: property Rs. 80L, rent Rs. 25,000/month")
    assert result["type"] == "help"  # documented behaviour: no crash, no wrong numbers


def test_gemini_tool_declares_every_field_the_extractor_reads():
    params = set(inspect.signature(le.parse_real_estate_query).parameters)
    assert set(EMPTY) <= params
