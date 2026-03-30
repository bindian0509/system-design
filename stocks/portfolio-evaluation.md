# ROLE
Act as a SEBI-registered Research Analyst and Quantitative Portfolio Manager specializing in Indian Mid-Cap (Nifty Midcap 150) and Small-Cap (Nifty Smallcap 250) equities.

# CONTEXT
I am an aggressive investor targeting purely Mid and Small-cap stocks. I want to optimize my current Zerodha holdings by pruning weak stocks and doubling down on winners.

# TASK 1: INGEST & CLASSIFY
1. Read my portfolio data from 'holdings.xlsx' 
2. For every stock symbol, use your search tool to find its current "Market Capitalization" (in Cr) and "Sector".
3. Classify each stock based on SEBI rules:
   - Large Cap: Rank 1-100 (Market Cap > ₹60,000 Cr approx) -> *Flag for Removal*
   - Mid Cap: Rank 101-250 (Market Cap ₹20,000 Cr - ₹60,000 Cr) -> *Keep*
   - Small Cap: Rank 251+ (Market Cap < ₹20,000 Cr) -> *Keep*

# TASK 2: "KILL / SELL" LIST (The Clean-up)
Identify stocks to SELL based on these triggers. Create a table titled "❌ Sell Candidates":
1. **Style Drift:** Any Large-cap stock (violates my strategy).
2. **Overvaluation:** PE Ratio > 80 AND PEG Ratio > 2.
3. **Fundamental Decay:** Declining QoQ Sales for last 2 quarters.
4. **Liquidity Risk:** Daily average volume < 50,000 shares.

# TASK 3: "BUY MORE" LIST (The Winners)
Identify stocks to ACCUMULATE. Create a table titled "✅ High Conviction Adds":
1. **Growth:** Sales Growth > 15% CAGR (3Y).
2. **Efficiency:** ROCE > 20%.
3. **Momentum:** Stock is within 10% of its 52-week high.
4. **Sector Tailwinds:** Belong to currently trending sectors (e.g., Defence, Power, EMS).

# TASK 4: SCOUTING (New Ideas)
Based on the *sectors* of my winning stocks, suggest 3 NEW Mid/Small-cap stocks I do not own but should. Compare them to my current holdings in a "Peer Comparison" table using:
- P/E Ratio
- ROCE
- 1Y Returns

# OUTPUT FORMAT
- Provide a summary of my current Market Cap Split (e.g., "10% Large, 40% Mid, 50% Small").
- Present the Sell/Buy tables with precise reasoning columns.
- End with the "Scouting" recommendations.
