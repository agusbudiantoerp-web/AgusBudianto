# AI Equity Research V1

Shared Python research engine for Streamlit web app and Telegram bot. Initial focus: IDX tickers using Yahoo Finance suffix .JK.

## Features
- Market history and price snapshot
- Available company and financial statement fields
- SMA 20/50/200, RSI 14 and historical annualized volatility
- Simplified illustrative DCF when free cash flow is available
- Excel report: summary, fundamentals, price history and DCF worksheets
- PDF report: snapshot, fundamentals, DCF availability and limitations
- Telegram command: /analyze ANTM

## Local setup (Windows PowerShell)
~~~powershell
cd Projects/ai-equity-research
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
~~~

## Telegram bot local test
1. Create a bot with Telegram BotFather and copy its token.
2. Keep the token private. Never commit it to GitHub.
3. In PowerShell:
~~~powershell
$env:TELEGRAM_BOT_TOKEN="PASTE_YOUR_TOKEN_HERE"
python bot.py
~~~
4. Send /start, then /analyze ANTM.

## Free deployment
- Web app: Streamlit Community Cloud; set app root to this folder and entrypoint to app.py.
- Telegram: local polling for development. Continuous free worker availability is not guaranteed; free hosts may sleep or impose limits.
- GitHub Pages cannot run Python bots. No paid AI API is required for the initial calculation engine.

## Data and model limitations
- Yahoo Finance is third-party data, not official IDX data. Coverage, timing, ticker history and statement fields can vary.
- Missing data is unavailable, not zero.
- Financial statement figures may use different units, currencies and reporting periods. Verify units and periods before interpreting ratios or valuation.
- DCF is a simplified aggregate enterprise-value illustration using available free cash flow. It is not a per-share fair value and does not yet normalize working capital, taxes, diluted shares, net debt, minority interests or segment forecasts.
- RSI and moving averages are technical indicators, not standalone trading signals.
- This tool is not investment advice. Validate all inputs and calculations independently.

## Next development gates
1. Add unit tests and live ticker checks.
2. Validate financial statement field mapping and units for Indonesian issuers.
3. Add per-share valuation, peer multiples, bear/base/bull cases and source-quality flags.
4. Add Telegram access control, webhook deployment and secret management.
5. Integrate a link into the existing portfolio only after tests pass.
