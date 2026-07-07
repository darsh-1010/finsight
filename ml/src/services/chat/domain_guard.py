"""Domain Guardrail — Financial domain classification module.

Single-responsibility module: decides whether a user query is within the
financial domain before any tier-specific processing runs.

Architecture
------------
- ``DomainDecision``  — Pydantic structured-output schema (guaranteed types)
- ``_fast_reject``    — Layer 1 regex pre-filter (< 1ms, no LLM): blocks obvious
                        build/architect/explain-tech patterns
- ``DOMAIN_CLASSIFIER_PROMPT`` — Layer 2 allowlist-based LLM classifier: maps query
                        to one of 8 supported financial intents or blocks it
- ``DomainGuard``     — async orchestrator: Layer1 → Layer2 → fail-open, timeout

Usage
-----
    from src.services.chat.domain_guard import DomainGuard

    guard = DomainGuard(fast_llm, history_service)
    decision = await guard.classify(message, session_id)
    if decision.should_block:
        return refusal_response
"""

import asyncio
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layer 1 — Fast regex pre-filter (< 1ms, no LLM call)
#
# Architecture:
#   1. _PERSONAL_FINANCE_BUILD — checked FIRST; if matched, always PASS
#      (guards "build a portfolio", "build an emergency fund", etc.)
#   2. _FAST_REJECT_PATTERN — if matched and step 1 didn't fire, BLOCK
#   3. Everything else → PASS to Layer 2 (LLM allowlist)
#
# Design principle: regex only catches unambiguous cases.
# Semantically ambiguous queries (e.g. "describe how a robo-advisor works
# technically") are intentionally left for the LLM classifier.
# ---------------------------------------------------------------------------

# Personal-finance build patterns that must NEVER be blocked by Layer 1.
# "build an emergency fund", "grow my portfolio", "develop an investment strategy"
# are finance goals, not software engineering requests.
_PERSONAL_FINANCE_BUILD = re.compile(
    r"\b(build|grow|create|develop|make|establish|set\s+up|engineer|design|craft|form)\b.{0,60}"
    r"\b(emergency\s+funds?|retirement\s+funds?|savings?\s+funds?|nest\s+egg|"
    r"emergency\s+savings|financial\s+cushion|war\s+chest|"
    r"investment\s+strateg(?:y|ies)|financial\s+strateg(?:y|ies)|financial\s+plan|"
    r"investment\s+plan|diversified\s+portfolio|stock\s+portfolio|bond\s+portfolio)\b",
    re.IGNORECASE,
)

# Portfolio-build shorthand: "build a portfolio", "grow my portfolio"
_PORTFOLIO_BUILD = re.compile(
    r"\b(build|create|grow|construct|develop|make)\b.{0,30}\bportfolio\b",
    re.IGNORECASE,
)

_FAST_REJECT_PATTERN = re.compile(
    r"\b("
    # ── Build / architect / design synonyms ───────────────────────────────────
    r"how\s+to\s+(build|make|create|design|architect|implement|set\s+up|develop|construct|engineer|write|assemble|compose|fabricate)\b"
    r"|how\s+(do\s+I|would\s+(I|one|you)|can\s+I)\s+(build|make|create|design|architect|implement|develop|construct|set\s+up|engineer|write|assemble|compose)\b"
    r"|help\s+me\s+(architect|design|build|create|implement|develop|code|program|engineer|write|assemble|compose)\b"
    r"|walk\s+me\s+through\s+(building|creating|designing|constructing|implementing|developing|coding|engineering|writing)\b"
    r"|walk\s+me\s+through\s+(the\s+)?(approach|process|methodology|steps)\s+(to|for)\s+(building|creating|designing|implementing|developing|making|engineering|writing|coding|constructing)\b"
    r"|guide\s+me\s+(through|on)\s+(building|creating|designing|making|developing|implementing|engineering)\b"
    r"|steps?\s+to\s+(build|create|design|develop|implement|architect|engineer|write|assemble)\b"
    r"|roadmap\s+(for|to)\s+(building|developing|creating|designing|implementing|engineering)\b"
    r"|what\s+(does\s+it\s+take|goes\s+into)\s+to\s+(build|create|design|develop|implement|engineer)\b"
    r"|I\s+want\s+to\s+(build|create|design|develop|implement|make|architect|engineer|write|assemble)\s+(a|an|the)\b"
    r"|I\s+am\s+(building|creating|developing|designing|implementing|making|engineering|writing)\s+(a|an|the)\b"
    # "build/create/develop a [X] platform|app|system|tool|bot|tracker|service|software"
    r"|(?:build|create|make|develop|construct|design|engineer|write|assemble)\s+(?:a|an|the)\s+\w+\s*"
    r"(platform|application|app|chatbot|bot|system|tool|service|dashboard|tracker|software|product|solution)\b"
    # Soft phrasings: "approach to creating", "methodology for developing", "systematic approach to building"
    r"|methodology\s+(to|for|behind|of)\s+(building|creating|designing|implementing|developing|making|engineering|writing|coding)\b"
    r"|systematic\s+(approach|process|way|method)\s+(to|for)\s+(building|creating|developing|designing|implementing|making|engineering|writing|coding)\b"
    r"|what('s|s|\s+is)\s+the\s+(best\s+)?(approach|methodology|process|way|method)\s+(to|for)\s+(building|creating|developing|designing|implementing|making|engineering)\b"
    r"|help\s+me\s+automate\b"
    # ── Software architecture / system design ─────────────────────────────────
    r"|architecture\s+(for|of|behind)\b"
    r"|software\s+(design|architecture|components?|structure)\b"
    r"|what\s+(are\s+the\s+)?(main\s+)?components\s+of\s+(a|an|the)\b"
    r"|break\s+down\s+the\s+components\b"
    r"|what\s+microservice\b"
    r"|data\s+pipeline\s+(for|of|behind)\b"
    r"|(infrastructure|tech\s+stack|technology\s+stack)\s+(of|for|behind|used\s+by)\b"
    r"|software\s+design\s+of\b"
    # ── Programming languages / tools / libraries ─────────────────────────────
    r"|tech(?:nology)?\s+stack\s+(for|of|used|behind)\b"
    r"|(programming\s+language|coding\s+language)\s+(should|to|for|do|used)\b"
    r"|which\s+(programming\s+languages?|languages?|libraries|frameworks|tools?)\s+(do|should|to|for|quant|trader|developer|use)\b"
    r"|(what|which)\s+librar(?:y|ies)\s+(should|to|for|do)\b"
    r"|(what|which)\s+frameworks?\s+(should|to|for|do|is\s+best)\b"
    r"|best\s+(framework|library|language|stack|tool|approach)\s+for\b"
    r"|recommend\s+(a\s+)?(tool|library|framework|language|stack)\b"
    r"|how\s+to\s+code\b"
    # ── General technology explanations ───────────────────────────────────────
    # "explain X" — covers ML, AI, infra, cloud, etc.
    r"|explain\s+(a\s+|an\s+)?(machine\s+learning|artificial\s+intelligence|deep\s+learning"
    r"|neural\s+networks?|nlp|natural\s+language\s+processing|transformers?\s*(model)?|"
    r"llm|large\s+language\s+models?|gpt|bert|reinforcement\s+learning|supervised\s+learning"
    r"|unsupervised\s+learning|blockchain|cloud\s+computing|kubernetes|docker|microservice"
    r"|rest\s+api|graphql|apis?)\b"
    # "what is (a/an) X"
    r"|what\s+is\s+(a\s+|an\s+)?(machine\s+learning|artificial\s+intelligence|deep\s+learning"
    r"|neural\s+networks?\s*(model)?|nlp|natural\s+language\s+processing|transformers?\s*(model)?"
    r"|llm|large\s+language\s+models?|python|java|javascript|typescript|blockchain|"
    r"cloud\s+computing|kubernetes|docker|apis?|database|sql|nosql|redis|mongodb|"
    r"postgresql|reinforcement\s+learning|supervised\s+learning|unsupervised\s+learning)\b"
    # "what is the difference between [tech] and [tech]"
    r"|what\s+is\s+the\s+difference\s+between\s+(supervised|unsupervised|deep|machine|reinforcement)\b"
    # "how does X work"
    r"|how\s+does?\s+(a\s+|an\s+)?(machine\s+learning|artificial\s+intelligence|deep\s+learning"
    r"|neural\s+networks?|nlp|natural\s+language\s+processing|blockchain|kubernetes|docker"
    r"|rest\s+api|apis?)\s+(work|learn|function|operate)\b"
    # ── Adversarial / jailbreak ───────────────────────────────────────────────
    r"|pretend\s+(you\s+are|to\s+be)\s+a?\s*(software|tech|system|developer|engineer|architect|coder|programmer)\b"
    r"|imagine\s+you\s*(?:'re|re|\s+are|\s+were|\s+could\s+be)\s*(a\s+|an\s+)?(software|tech|fintech|system|developer|engineer|architect|coder|programmer)\b"
    r"|respond\s+as\s+(a\s+)?(software|tech|fintech|quant|developer|engineer|architect|programmer)\b"
    r"|act\s+as\s+(a\s+)?(software|tech|fintech|developer|engineer|architect|coder|programmer)\b"
    r"|from\s+a\s+(technical|engineering|software|developer|system\s+design)\s+(standpoint|perspective|angle|view)\b"
    r"|ignore\s+(previous|prior|all)?\s*instructions?\b"
    r"|as\s+(a\s+)?(software|tech|fintech)\s+(architect|engineer|developer|lead|director)\b"
    r")",
    re.IGNORECASE,
)


def _fast_reject(message: str) -> bool:
    """Return True if the message should be blocked immediately (Layer 1).

    Personal-finance build patterns are checked first and always pass through
    so "build a portfolio" / "build an emergency fund" are never false-positived.
    Semantically ambiguous cases (e.g. "describe how a robo-advisor works
    technically") pass through to the LLM classifier at Layer 2.
    """
    # Step 1: personal-finance build goals are never blocked at regex level
    if _PERSONAL_FINANCE_BUILD.search(message) or _PORTFOLIO_BUILD.search(message):
        return False
    # Step 2: reject if an off-domain pattern matches
    return bool(_FAST_REJECT_PATTERN.search(message))


# ---------------------------------------------------------------------------
# Schema — structured output returned by gpt-4.1-mini
# ---------------------------------------------------------------------------


class DomainDecision(BaseModel):
    """Structured output from the financial domain classifier.

    All fields are guaranteed types — no JSON parsing, no string booleans.
    """

    is_financial: bool = Field(
        description=(
            "True if the query's PRIMARY OUTCOME serves a financial decision, "
            "understanding, or analysis — regardless of what other topics it touches. "
            "False if it primarily seeks knowledge or assistance in a domain unrelated "
            "to finance with no meaningful financial outcome."
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the classification. "
            "1.0 = completely certain. 0.5 = genuinely ambiguous. "
            "Use 0.5–0.7 for very short follow-ups that depend heavily on context."
        ),
    )
    reason: str = Field(
        description=(
            "One sentence (max 150 chars) explaining WHY this is or is not financial. "
            "Used for audit logging and debugging."
        ),
    )

    @property
    def should_block(self) -> bool:
        """Return True if the guardrail should block this query.

        Block only when:
          - LLM is confident the query is off-domain (confidence ≥ 0.70), AND
          - is_financial is False

        Fail-open below the threshold: short follow-ups and ambiguous queries
        (confidence < 0.70) are allowed through — the main LLM handles them.
        The 0.70 threshold reduces exploit risk from adversarial edge cases that
        deliberately aim to land in the 0.65–0.70 ambiguous range.
        """
        return not self.is_financial and self.confidence >= 0.70


# ---------------------------------------------------------------------------
# Production-grade domain classifier prompt
# ---------------------------------------------------------------------------

DOMAIN_CLASSIFIER_PROMPT = """\
You are a strict domain guardrail for a Financial Intelligence Assistant.
Your sole task: determine whether a user query maps to one of the SUPPORTED INTENTS below.
If it does not clearly map to a supported intent, it is OUT-OF-DOMAIN.

════════════════════════════════════════════════════════════════
 THE SINGLE TEST TO APPLY BEFORE ANYTHING ELSE
════════════════════════════════════════════════════════════════
Ask yourself: "Does a FINANCIAL EXPERT (analyst, advisor, economist) provide the
most valuable answer to this question?"

  YES → likely IN-DOMAIN  (financial knowledge drives the answer)
  NO  → likely OUT-OF-DOMAIN  (software engineer, career coach, or teacher answers)

Examples of the test in action:
  "How does algorithmic trading affect liquidity?" → Financial expert ✓ → IN-DOMAIN
  "What engineering is involved in an HFT system?" → Software engineer ✗ → OUT-OF-DOMAIN
  "What technology stack do hedge funds use?" → IT/infra professional ✗ → OUT-OF-DOMAIN
  "What programming languages do quant traders use?" → Software/career coach ✗ → OUT-OF-DOMAIN

════════════════════════════════════════════════════════════════
 SUPPORTED INTENTS — the ONLY things this assistant answers
════════════════════════════════════════════════════════════════
1. stock_and_market_analysis
   Stock prices, valuations, earnings, ETFs, options, sector trends, market
   indices, dividends, IPOs, short-selling, forex, commodities, crypto as asset class.
   PASS: "Is Apple overvalued?", "Why did the S&P 500 drop?", "What are Bitcoin's risks?"
   BLOCK: "How do I build a stock screener?" → software, not analysis

2. company_fundamentals
   Revenue, margins, P/E ratio, EV/EBITDA, competitive positioning, M&A,
   management quality, earnings reports, balance sheets, cash flow.
   PASS: "Tesla revenue trends?", "Compare AAPL vs MSFT margins"
   BLOCK: "How do I scrape earnings data?" → coding task

3. macroeconomics
   Interest rates, inflation, central bank policy (Fed, ECB), GDP, recession
   signals, yield curves, tariffs, trade policy, currency dynamics, QE/QT.
   PASS: "How do rising rates affect bonds?", "What is CBDC's impact on monetary policy?"
   BLOCK: "How does a central bank payment system work technically?" → infra/tech

4. personal_finance
   Budgeting, savings rate, debt payoff, mortgages, retirement (IRA, 401k, pension),
   tax planning, insurance, credit scores, net worth, estate planning, emergency funds.
   PASS: "How do I build a 6-month emergency fund?", "Should I pay off debt or invest?"
   BLOCK: "How do I build a personal finance app?" → software

5. portfolio_strategy
   Asset allocation, diversification, risk management, rebalancing, factor
   investing, ESG, hedging, portfolio theory, backtesting strategies (the financial
   logic of what to test, not how to code the backtester).
   PASS: "How should I rebalance my portfolio?", "How do I backtest a momentum strategy?"
   BLOCK: "How do I code a backtesting engine in Python?" → coding

6. financial_concepts
   Definitions and explanations of finance-native terms, instruments, and
   MARKET MECHANISMS — where the answer requires financial domain expertise.
   PASS: "What is ROIC?", "Explain compound interest", "How does a market maker work?",
         "What is algorithmic trading?", "How does high-frequency trading affect markets?",
         "What are dark pools?", "Explain market microstructure", "What is the carry trade?",
         "How does a robo-advisor manage assets?", "What is systematic vs discretionary trading?"
   BLOCK: "Explain machine learning" → general tech, a CS teacher answers this
   BLOCK: "How does NLP work?" → general tech
   BLOCK: "Describe how a robo-advisor works technically" → software architecture
   BLOCK: "What is fintech?" → industry overview, not a financial analysis concept
   BLOCK: "What engineering is in a trading platform?" → software engineer answers this

   CRITICAL SUB-RULE — mechanism vs. implementation:
     "How does X work?" is IN-DOMAIN if X is a FINANCIAL MECHANISM (algo trading,
      dark pools, market making, options pricing, yield curves).
     "How does X work?" is OUT-OF-DOMAIN if X is a SOFTWARE SYSTEM or TECHNOLOGY
      (trading platform, robo-advisor software, data pipeline, API, tech stack).

7. financial_document_analysis
   Analysis of uploaded financial documents: earnings reports, SEC filings,
   balance sheets, income statements, financial news, research reports.
   PASS: "Analyze this balance sheet", "Summarize this earnings report"
   BLOCK: "Analyze this Python code" → code review, not finance

8. finsight_identity
   Questions about this assistant's capabilities or identity.
   PASS: "What can you do?", "Who are you?", "What topics do you cover?"

════════════════════════════════════════════════════════════════
 EXPLICIT OUT-OF-DOMAIN CATEGORIES
════════════════════════════════════════════════════════════════
These are NEVER in-domain regardless of financial keywords present:

A. SOFTWARE / ENGINEERING REQUESTS
   Building, designing, architecting, implementing any software — even if
   "finance" or "trading" is in the query.
   BLOCK: "How to build a trading bot", "What engineering is in an HFT system?",
          "Design a market data pipeline", "What microservices does a trading system need?",
          "Recommend tools for building a trading bot", "Software design of a fintech app"

B. TECHNOLOGY STACK / TOOLS / PROGRAMMING LANGUAGES
   Which language/library/framework/tool to use — software career/tooling decisions.
   BLOCK: "What tech stack do hedge funds use?", "Which programming languages do quant
          traders use?", "What Python libraries should I use for quant finance?",
          "Compare Python vs R for finance", "Best framework for a trading app"

C. GENERAL TECHNOLOGY EXPLANATIONS
   Explaining a technology concept where a CS teacher, not a financial analyst, answers.
   BLOCK: "Explain machine learning", "What is AI?", "How do APIs work?",
          "What is a database?", "Explain blockchain", "How does Docker work?",
          "What is cloud computing?", "Explain neural networks", "What is NLP?"
   EXCEPTION: "What is crypto / Bitcoin as an investment?" → stock_and_market_analysis ✓
              "What are the risks of investing in crypto?" → stock_and_market_analysis ✓
              "Explain blockchain in the context of crypto as an asset class" → ✓
              (The ASSET and INVESTMENT angle makes it financial, even if blockchain
               technology is mentioned. But "explain blockchain" alone → BLOCK.)

D. INDUSTRY OVERVIEW / FINTECH-AS-A-SECTOR QUESTIONS
   Broad "what is this industry/field" questions with no financial analysis outcome.
   BLOCK: "Explain fintech as an industry", "What is fintech?",
          "What does the financial services industry look like?"
   EXCEPTION: "Which fintech stocks are undervalued?" → stock_and_market_analysis ✓
              "How is fintech disrupting traditional banking revenue?" → company_fundamentals ✓

E. CAREER / JOB DESCRIPTION QUESTIONS
   How to enter, advance in, or understand a finance career — not financial analysis.
   BLOCK: "How do I become a quantitative analyst?", "What does a hedge fund manager do?",
          "What is the difference between a quant and a trader?",
          "What skills do I need to work in finance?"

F. DEVELOPER / BUILDER FRAMING
   When the user identifies as a developer or frames the question as a technical build.
   BLOCK: "As a developer, I need to understand the finance domain",
          "I am building a fintech product, explain the domain",
          "From a technical standpoint, how would you structure this?"

════════════════════════════════════════════════════════════════
 CONTRAST EXAMPLES — highest-confusion pairs
════════════════════════════════════════════════════════════════
PASS  "How does algorithmic trading affect market liquidity?" → financial mechanism
BLOCK "What engineering is involved in an HFT system?" → software engineering

PASS  "How does a robo-advisor manage portfolio allocation?" → financial logic
BLOCK "Describe how a robo-advisor works technically" → software architecture

PASS  "How do quant hedge funds use machine learning to generate alpha?" → financial outcome
BLOCK "What technology stack do hedge funds use?" → IT infrastructure

PASS  "What is systematic trading?" → financial_concepts
BLOCK "What programming languages do systematic traders use?" → software tooling

PASS  "How do I backtest a momentum strategy?" → portfolio_strategy (financial logic)
BLOCK "How do I build a backtesting engine in Python?" → coding

PASS  "What is crypto as an asset class and its risks?" → stock_and_market_analysis
BLOCK "Explain blockchain" → general tech

PASS  "How does a CBDC affect monetary policy?" → macroeconomics
BLOCK "How does a central bank payment system work technically?" → tech infrastructure

PASS  "What is a market maker and how do they profit?" → financial_concepts
BLOCK "Recommend tools for building a market maker bot" → software tools

════════════════════════════════════════════════════════════════
 REFERENCE RESOLUTION (multi-turn accuracy)
════════════════════════════════════════════════════════════════
If the query uses pronouns or implicit references ("they", "their", "it",
"that company", "why did it drop") pointing to a company, stock, or financial
topic in the [Conversation History] below — resolve the reference FIRST, then
classify against the 8 intents.

Example:
  History: "User asked about Apple Inc. earnings"
  Query: "What is their P/E ratio?" → resolve to Apple → company_fundamentals ✓

════════════════════════════════════════════════════════════════
 CONFIDENCE CALIBRATION
════════════════════════════════════════════════════════════════
0.95–1.00  Absolutely certain (clean match or clear non-match)
0.80–0.94  High confidence (minor cross-domain element, primary intent clear)
0.65–0.79  Moderate — cross-domain, but primary outcome is identifiable
0.50–0.64  Genuinely ambiguous short follow-up → fail-open: is_financial: true
< 0.50     Cannot decide → is_financial: true (fail-open always)

════════════════════════════════════════════════════════════════
 FAIL-OPEN RULE
════════════════════════════════════════════════════════════════
Fail-open (is_financial: true) applies ONLY to RULE 3 — very short, context-
dependent follow-ups where the previous turn was financial.
For clearly out-of-domain queries — software/engineering, tech explanations,
career questions, developer framing — use is_financial: false, confidence ≥ 0.90.
When finance keywords appear in a software/tech question, the SOFTWARE FRAMING wins.
"""


# ---------------------------------------------------------------------------
# DomainGuard — async classifier
# ---------------------------------------------------------------------------

_CLASSIFIER_TIMEOUT_SECONDS = 8.0
_HISTORY_TURNS = 4  # number of messages (2 full turns) for reference resolution


class DomainGuard:
    """Async domain classifier for the financial chatbot.

    Wraps an OpenAI structured-output call with:
      - conversation history context (for pronoun/reference resolution)
      - asyncio timeout (fail-open after 8s so no request hangs)
      - full fail-open on any exception

    Instantiate once per ``ChatService`` instance and reuse.

    Example::

        guard = DomainGuard(fast_llm, history_service)
        decision = await guard.classify(message, session_id)
        if decision.should_block:
            return build_refusal()
    """

    def __init__(self, fast_llm: ChatOpenAI, history_service) -> None:  # type: ignore[type-arg]
        self._fast_llm = fast_llm
        self._history_service = history_service
        # Build the structured-output chain once; reuse across calls
        self._classifier = fast_llm.with_structured_output(DomainDecision)

    async def classify(
        self,
        message: str,
        session_id: str | None = None,
    ) -> DomainDecision:
        """Classify whether ``message`` is within the financial domain.

        Args:
            message:    The sanitised user message (will be truncated to 600 chars).
            session_id: If provided, loads recent conversation history for
                        reference resolution (pronouns, follow-up queries).

        Returns:
            A ``DomainDecision`` with ``is_financial``, ``confidence``,
            ``reason``, and the ``should_block`` convenience property.

        This method **never raises**. On any failure it returns a fail-open
        decision (``is_financial=True``) so legitimate queries are never
        silently dropped.
        """
        # Layer 1 — fast regex pre-filter (no LLM call)
        if _fast_reject(message):
            logger.info(
                "[DOMAIN_GUARD] Layer1-fast-reject | session=%s | query=%.80s",
                session_id,
                message,
            )
            return DomainDecision(
                is_financial=False,
                confidence=0.95,
                reason="Fast-reject: build/architect/explain-tech pattern matched.",
            )

        try:
            history_block = await self._build_history_block(session_id)
            system_content = DOMAIN_CLASSIFIER_PROMPT + history_block

            decision: DomainDecision = await asyncio.wait_for(
                self._classifier.ainvoke(
                    [
                        SystemMessage(content=system_content),
                        HumanMessage(content=f"Classify this query: {message[:600]}"),
                    ]
                ),
                timeout=_CLASSIFIER_TIMEOUT_SECONDS,
            )

            logger.info(
                "[DOMAIN_GUARD] session=%s | is_financial=%s | confidence=%.2f | reason=%s",
                session_id,
                decision.is_financial,
                decision.confidence,
                decision.reason,
            )
            return decision

        except asyncio.TimeoutError:
            logger.warning(
                "[DOMAIN_GUARD] Classifier timed out after %.1fs — failing open | session=%s",
                _CLASSIFIER_TIMEOUT_SECONDS,
                session_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "[DOMAIN_GUARD] Classifier error (%s) — failing open | session=%s",
                exc,
                session_id,
            )

        return DomainDecision(
            is_financial=True,
            confidence=1.0,
            reason="Classifier unavailable — failing open.",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_history_block(self, session_id: str | None) -> str:
        """Fetch recent conversation turns for reference resolution context."""
        if not session_id:
            return ""
        try:
            history = await self._history_service.get_history_messages(
                session_id, is_new=False
            )
            if not history:
                return ""
            lines = []
            for h_msg in history[-_HISTORY_TURNS:]:
                role = "User" if h_msg.type == "human" else "Assistant"
                lines.append(f"{role}: {h_msg.content[:300]}")
            return (
                "\n\n[Conversation History — use for reference resolution]\n"
                + "\n".join(lines)
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(
                "[DOMAIN_GUARD] History fetch failed (%s) — continuing without context",
                exc,
            )
            return ""
