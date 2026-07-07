import pytest
from src.utils.postprocessor import ResponsePostprocessor

@pytest.fixture
def postprocessor():
    return ResponsePostprocessor()

def test_extract_citations_from_text(postprocessor):
    text = "Check out [Google](https://google.com) and [OpenAI](https://openai.com)."
    citations = postprocessor.extract_citations_from_text(text)
    
    assert len(citations) == 2
    assert citations[0]["title"] == "Google"
    assert citations[0]["url"] == "https://google.com"

def test_estimate_confidence(postprocessor):
    # Case 1: High confidence (financial data + citations)
    conf_high = postprocessor.estimate_confidence(
        has_financial_context=True,
        has_citations=True,
        citation_count=3,
        used_web_search=False
    )
    assert conf_high >= 0.9
    
    # Case 2: Low confidence (web search fallback, no financial data)
    conf_low = postprocessor.estimate_confidence(
        has_financial_context=False,
        has_citations=False,
        citation_count=0,
        used_web_search=True
    )
    assert conf_low <= 0.5

def test_validate_financial_context_sanity(postprocessor):
    bad_data = {
        "AAPL": {
            "current_price": 1000000, # Unrealistic
            "pe_ratio": 10000 # Unrealistic for AAPL but within SANITY_RANGES maybe?
        }
    }
    # Current SANITY_RANGES for price is (0.001, 100,000)
    # So 1,000,000 should trigger a warning
    
    _, warnings = postprocessor.validate_financial_context(bad_data)
    assert len(warnings) > 0
    assert any("AAPL" in w and "current_price" in w for w in warnings)
