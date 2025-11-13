"""Main CLI entry point for Betting Expert Advisor."""
import argparse
import sys

from src.adapters.theodds_api import TheOddsAPIAdapter
from src.config import settings
from src.data_fetcher import DataFetcher, MockDataSource
from src.db import init_db
from src.executor import Executor
from src.feature import build_features
from src.ml_pipeline import MLPipeline
from src.model import ModelWrapper
from src.strategy import find_value_bets
from src.tools.synthetic_data import generate_complete_dataset
from src.logging_config import get_logger
from src.utils import setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


def cmd_fetch(args):
    """Fetch data from configured source."""
    logger.info("=== Fetch Mode ===")

    # Use TheOddsAPI if API key is configured, otherwise use mock data
    if settings.THEODDS_API_KEY:
        logger.info("Using TheOddsAPI (live data)")
        source = TheOddsAPIAdapter(api_key=settings.THEODDS_API_KEY)
    else:
        logger.warning("No THEODDS_API_KEY found, using mock data")
        source = MockDataSource()

    fetcher = DataFetcher(source=source)
    fixtures = fetcher.get_fixtures()

    logger.info(f"Fetched {len(fixtures)} fixtures")
    print(fixtures.head(10))

    if not fixtures.empty:
        market_ids = fixtures["market_id"].tolist()[:5]
        odds = fetcher.get_odds(market_ids)
        logger.info(f"Fetched {len(odds)} odds entries")
        print(odds.head(10))


def cmd_train(args):
    """Train ML model."""
    logger.info("=== Train Mode ===")

    # Generate synthetic training data
    logger.info("Generating synthetic training data...")
    fixtures, odds, results = generate_complete_dataset(n_days=180, games_per_day=10)

    # Build features first (before merging everything)
    logger.info("Building features...")
    features = build_features(fixtures, odds)

    # Now merge with results to get labels
    features = features.merge(results, on="market_id", how="left")

    # Create binary labels (1 if home won, 0 otherwise)
    # We need to match the selection in features with the result
    # For now, let's predict if home wins
    features["label"] = (features["result"] == "home").astype(int)

    # Remove rows with missing labels
    features = features.dropna(subset=["label"])

    logger.info(f"Training on {len(features)} samples")

    # Choose training method
    if args.advanced:
        # Use advanced pipeline with CV and hyperparameter tuning
        pipeline = MLPipeline()
        labels = features["label"].values
        features_only = features.drop(columns=["label", "market_id"], errors="ignore")
        pipeline.train_with_cv(features_only, labels, n_splits=5, n_trials=20)
        logger.info("Advanced model trained with cross-validation")
    else:
        # Use simple model training
        model = ModelWrapper()
        labels = features["label"].values
        features_only = features.drop(columns=["label", "market_id"], errors="ignore")
        X = features_only.select_dtypes(include=["number"]).fillna(0).values
        model.train(X, labels)
        logger.info("Simple model trained")


def cmd_simulate(args):
    """Run simulation/backtest."""
    logger.info("=== Simulate Mode ===")

    # Initialize database
    init_db()

    # Get data
    fetcher = DataFetcher()
    fixtures = fetcher.get_fixtures()

    if fixtures.empty:
        logger.warning("No fixtures available for simulation")
        return

    market_ids = fixtures["market_id"].tolist()
    odds = fetcher.get_odds(market_ids)

    # Build features
    logger.info("Building features...")
    features = build_features(fixtures, odds)

    # Add dummy probabilities for demonstration
    # In production, load trained model and predict
    features["p_win"] = 0.55  # Placeholder

    # Find value bets
    logger.info("Finding value bets...")
    bets = find_value_bets(features, proba_col="p_win", odds_col="odds", bank=args.bankroll)

    logger.info(f"Found {len(bets)} value bets")

    # Execute bets in dry-run mode
    executor = Executor()
    results = []

    for bet in bets:
        logger.info(
            f"Simulating: {bet['home']} vs {bet['away']} - "
            f"{bet['selection']} @ {bet['odds']:.2f} for ${bet['stake']:.2f}"
        )
        result = executor.execute(bet, dry_run=True)
        results.append(result)

    logger.info(f"Simulation complete: {len(results)} bets executed")


def cmd_place(args):
    """Place bets (DRY-RUN or LIVE)."""
    is_dry_run = args.dry_run or settings.MODE == "DRY_RUN"

    logger.info(f"=== Place Mode ({'DRY-RUN' if is_dry_run else 'LIVE'}) ===")

    if not is_dry_run:
        logger.warning("!!! LIVE MODE - REAL MONEY AT RISK !!!")
        response = input("Are you sure you want to place LIVE bets? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Aborted by user")
            return

    # Initialize database
    init_db()

    # Get data
    fetcher = DataFetcher()
    fixtures = fetcher.get_fixtures()

    if fixtures.empty:
        logger.warning("No fixtures available")
        return

    market_ids = fixtures["market_id"].tolist()
    odds = fetcher.get_odds(market_ids)

    # Build features
    features = build_features(fixtures, odds)

    # Add predictions (placeholder - in production, load and run model)
    features["p_win"] = 0.55

    # Find value bets
    bets = find_value_bets(features, proba_col="p_win", odds_col="odds", bank=args.bankroll)

    if not bets:
        logger.info("No value bets found")
        return

    logger.info(f"Placing {len(bets)} bets...")

    # Execute bets
    executor = Executor()
    results = executor.execute_batch(bets, dry_run=is_dry_run)

    # Summary
    successful = sum(1 for r in results if r["status"] in ["accepted", "dry_run"])
    logger.info(f"Execution complete: {successful}/{len(results)} successful")


def cmd_serve(args):
    """Start monitoring API server."""
    logger.info("=== Serve Mode ===")

    import uvicorn

    from src.monitoring import app

    logger.info(f"Starting monitoring server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Betting Expert Advisor - Automated sports betting system"
    )

    parser.add_argument(
        "--mode",
        choices=["fetch", "train", "simulate", "place", "serve"],
        required=True,
        help="Operation mode",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate bet placement (no real money)"
    )

    parser.add_argument("--bankroll", type=float, default=1000.0, help="Current bankroll amount")

    parser.add_argument(
        "--advanced",
        action="store_true",
        help="Use advanced ML pipeline with hyperparameter tuning",
    )

    parser.add_argument("--host", default="0.0.0.0", help="Server host (for serve mode)")

    parser.add_argument("--port", type=int, default=8000, help="Server port (for serve mode)")

    args = parser.parse_args()

    # Log configuration
    logger.info(f"Starting Betting Expert Advisor (ENV={settings.ENV}, MODE={settings.MODE})")

    # Initialize database for all modes except fetch
    if args.mode != "fetch":
        init_db()
        logger.info("Database initialized")

    # Route to appropriate command
    try:
        if args.mode == "fetch":
            cmd_fetch(args)
        elif args.mode == "train":
            cmd_train(args)
        elif args.mode == "simulate":
            cmd_simulate(args)
        elif args.mode == "place":
            cmd_place(args)
        elif args.mode == "serve":
            cmd_serve(args)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
