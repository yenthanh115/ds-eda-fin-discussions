"""Test that catalog_risks no longer reports missing ticker column."""
import pandas as pd
from src.dataset_quality import catalog_risks

df = pd.read_csv("data/StockMarket_subreddit.csv", sep=";", index_col=0)
risks = catalog_risks(df, date_col="created_utc", ticker_col="ticker")

print("Risks found:")
for r in risks:
    print(f"  - {r}")

# Check the old message is gone
ticker_risk = [r for r in risks if "No ticker column" in r]
if ticker_risk:
    print("\nFAIL: ticker risk still present!")
else:
    print("\nOK: no 'missing ticker column' risk reported")
