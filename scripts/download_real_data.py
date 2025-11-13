"""Download real historical football data from football-data.co.uk."""
from pathlib import Path
import pandas as pd
import requests


def download_premier_league_data(seasons=["2324", "2223", "2122"]):
    """Download Premier League data from football-data.co.uk.

    Args:
        seasons: List of seasons (e.g., '2324' for 2023-24)

    Returns:
        DataFrame with all data
    """
    base_url = "https://www.football-data.co.uk/mmz4281"

    # Create data directory
    data_dir = Path("data/real")
    data_dir.mkdir(parents=True, exist_ok=True)

    all_data = []

    print("\n" + "=" * 70)
    print("  DOWNLOADING REAL HISTORICAL DATA")
    print("=" * 70 + "\n")

    for season in seasons:
        url = f"{base_url}/{season}/E0.csv"
        filepath = data_dir / f"premier_league_{season}.csv"

        print(f"📥 Downloading {season} season...")

        try:
            # Check if already downloaded
            if filepath.exists():
                print(f"   ✅ Already exists: {filepath}")
                df = pd.read_csv(filepath)
            else:
                # Download
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                # Save to file
                with open(filepath, "wb") as f:
                    f.write(response.content)

                print(f"   ✅ Downloaded: {filepath}")
                df = pd.read_csv(filepath)

            print(f"   📊 Matches: {len(df)}")
            all_data.append(df)

        except Exception as e:
            print(f"   ❌ Error downloading {season}: {e}")
            continue

    if not all_data:
        print("\n❌ No data downloaded!")
        return None

    # Combine all seasons
    combined = pd.concat(all_data, ignore_index=True)

    print(f"\n✅ Total matches downloaded: {len(combined)}")
    print(f"✅ Data saved to: {data_dir}")

    # Show available columns
    print(f"\n📊 Available columns ({len(combined.columns)}):")
    print("   Match info: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR")
    print(
        f"   Odds columns: {len([c for c in combined.columns if 'H' in c or 'D' in c or 'A' in c])}"
    )

    return combined


def convert_to_standard_format(df):
    """Convert football-data.co.uk format to our standard format.

    Args:
        df: Raw dataframe from football-data.co.uk

    Returns:
        fixtures, odds, results DataFrames
    """
    print("\n" + "=" * 70)
    print("  CONVERTING TO STANDARD FORMAT")
    print("=" * 70 + "\n")

    # Clean data
    df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTR"])

    # Parse dates
    try:
        df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y")
    except Exception:
        try:
            df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%y")
        except Exception:
            print("⚠️  Warning: Could not parse dates")

    # Create fixtures
    fixtures = []
    odds = []
    results = []

    for idx, row in df.iterrows():
        market_id = f"real_{idx}"

        # Fixture
        fixtures.append(
            {
                "market_id": market_id,
                "home": row["HomeTeam"],
                "away": row["AwayTeam"],
                "start": row["Date"],
                "sport": "soccer",
                "league": "Premier League",
            }
        )

        # Result
        result_map = {"H": "home", "D": "draw", "A": "away"}
        results.append(
            {
                "market_id": market_id,
                "result": result_map.get(row["FTR"], "unknown"),
                "home_score": row.get("FTHG"),
                "away_score": row.get("FTAG"),
            }
        )

        # Odds - use Bet365 as primary (B365), fallback to others
        odds_columns = {
            "home": ["B365H", "BWH", "PSH", "WHH", "VCH"],
            "draw": ["B365D", "BWD", "PSD", "WHD", "VCD"],
            "away": ["B365A", "BWA", "PSA", "WHA", "VCA"],
        }

        for outcome, cols in odds_columns.items():
            # Try each bookmaker in order
            odds_value = None
            provider = None

            for col in cols:
                if col in row and pd.notna(row[col]) and row[col] > 0:
                    odds_value = row[col]
                    provider = col[:4]  # Extract bookmaker name
                    break

            if odds_value:
                odds.append(
                    {
                        "market_id": market_id,
                        "selection": outcome,
                        "odds": float(odds_value),
                        "provider": provider,
                        "last_update": row["Date"],
                    }
                )

    fixtures_df = pd.DataFrame(fixtures)
    odds_df = pd.DataFrame(odds)
    results_df = pd.DataFrame(results)

    print(f"✅ Fixtures: {len(fixtures_df)}")
    print(f"✅ Odds: {len(odds_df)}")
    print(f"✅ Results: {len(results_df)}")

    # Save to CSV
    data_dir = Path("data/real")
    fixtures_df.to_csv(data_dir / "fixtures.csv", index=False)
    odds_df.to_csv(data_dir / "odds.csv", index=False)
    results_df.to_csv(data_dir / "results.csv", index=False)

    print(f"\n✅ Saved to {data_dir}/")
    print("   • fixtures.csv")
    print("   • odds.csv")
    print("   • results.csv")

    return fixtures_df, odds_df, results_df


def main():
    """Download and convert real data."""
    # Download data (last 3 seasons)
    raw_data = download_premier_league_data(seasons=["2324", "2223", "2122"])

    if raw_data is None:
        print("\n❌ Failed to download data")
        return 1

    # Convert to standard format
    fixtures, odds, results = convert_to_standard_format(raw_data)

    # Summary stats
    print("\n" + "=" * 70)
    print("  DATA SUMMARY")
    print("=" * 70 + "\n")

    print("📊 Seasons: 2021-22, 2022-23, 2023-24")
    print(f"📊 Total matches: {len(fixtures)}")
    print(f"📊 Date range: {fixtures['start'].min()} to {fixtures['start'].max()}")

    # Outcome distribution
    outcome_counts = results["result"].value_counts()
    print("\n📊 Outcomes:")
    for outcome, count in outcome_counts.items():
        pct = count / len(results) * 100
        print(f"   {outcome}: {count} ({pct:.1f}%)")

    # Odds availability
    markets_with_odds = odds.groupby("market_id").size()
    print("\n📊 Odds coverage:")
    print(f"   Markets with all 3 outcomes: {(markets_with_odds == 3).sum()}")
    print(f"   Average odds per market: {markets_with_odds.mean():.1f}")

    print("\n✅ Real data ready for testing!")
    print("\nNext step:")
    print("  python scripts/test_real_data.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
