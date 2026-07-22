"""Agentic Actionable-Inference layer (spec 14, owner: vayu-agents).

Turns VayuDrishti's published intelligence into verified, evidence-cited Action
Briefs via the hosted Nemotron NIM. Four roles run at publish time:
Situation Analyst -> Causal Strategist -> Action Drafter -> Adversarial Verifier.

Public surface:
- ``nim``: transport wrapper over the NIM endpoint (thinking mode, trace parse).
- ``smoke``: live one-shot API check (``python -m vayu.agents.smoke``), NOT a pytest.
"""
