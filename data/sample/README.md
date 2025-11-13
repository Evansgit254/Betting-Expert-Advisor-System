# Sample Data Directory

This directory is for sample/test datasets.

The system includes a synthetic data generator that creates realistic betting data for testing and backtesting.

## Generating Synthetic Data

```python
from src.tools.synthetic_data import generate_complete_dataset

# Generate fixtures, odds, and results
fixtures, odds, results = generate_complete_dataset(
    n_days=90,
    games_per_day=10,
    add_margin=0.05  # 5% bookmaker margin
)

# Save to CSV
fixtures.to_csv('data/sample/fixtures.csv', index=False)
odds.to_csv('data/sample/odds.csv', index=False)
results.to_csv('data/sample/results.csv', index=False)
```

## Using Real Data

For production use, replace the `MockDataSource` in `src/data_fetcher.py` with a real adapter:

1. Implement adapter in `src/adapters/` (e.g., `theodds_api.py`)
2. Configure API keys in `.env`
3. Update `DataFetcher` to use the real adapter

See `src/adapters/theodds_api.py` for a reference implementation.
