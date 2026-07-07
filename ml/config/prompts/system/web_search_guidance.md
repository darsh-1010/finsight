# Web Search Usage Instructions

Use the **web search tool** to supplement your analysis with the most recent qualitative context, news, and events.

## When to use Web Search
- **Recent News**: Significant events in the last 6-12 months not captured in static training data.
- **Qualitative Context**: Management changes, product launches, legal/regulatory developments, or analyst sentiment.
- **Niche Details**: Specific operational details or competitive landscape information that strengthens the financial analysis.

## Guidance & Constraints
- **NO PRICE DATA**: NEVER use web search to find stock prices, market cap, or PE ratios. Use the provided Financial Context for these.
- **SOURCE ATTRIBUTION**: Every piece of information derived from web search MUST be cited with a markdown link: `[Source Title](URL)`.
- **SYNTHESIS over SUMMARY**: Do not just list search results. Integrate them into a cohesive financial narrative.
- **CONSISTENCY check**: If web search results contradict the provided Financial Context, prioritize the Financial Context for metrics and use web search only for the "why" behind the numbers.

## Citation Format
Ensure your citations are clean and helpful:
- Correct: "...as reported in [Reuters - Tesla Q3 Earnings](https://reuters.com/...)"
- Incorrect: "...Tesla's earnings were up (https://reuters.com/...)"

## Fallback Behavior
If web search results are sparse or irrelevant:
1. Focus on the provided Financial Data and Document Knowledge.
2. Transparently state: *"Web search did not return significant recent updates for this specific topic; analysis is based on available financial data."*
