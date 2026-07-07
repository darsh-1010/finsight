# TASK: FINANCIAL INTENT & ENTITY EXTRACTION
**Raw User Query**: 
"{user_query}"

**Assignment Instructions**:
1. Deconstruct the query to identify primary and secondary entities (tickers or company names). If the query is a **personal finance or educational question** (e.g., budgeting, saving, emergency funds, debt management, retirement planning, compound interest, taxes, insurance, credit scores), there may be NO tickers or company names — this is **normal and expected**.
2. Determine the analytical intent (e.g., valuation, comparison, news inquiry, personal finance concept, financial education, budgeting advice).
3. **Reference Resolution**: If the query uses pronouns or implicit references (e.g., "they", "their", "it", "that company") that refer to a company, stock, or topic from earlier in this conversation, resolve those references to the specific entity before evaluating domain or entities. Such follow-up queries are **in-domain** if the referenced topic is financial.
4. Map the required data points to specific yFinance endpoints **if applicable**. For personal finance or educational questions, set `expanded_queries: []` — no yFinance data is needed. Set `is_financial: true`.
5. Respond with the standardized JSON structure.
6. **MANDATORY**: Generate 3-4 high-quality, non-generic follow-up questions **relevant to the user's specific query** (personal finance follow-ups for personal finance questions; equity follow-ups for stock questions).
