#!/usr/bin/env python3
"""CLI script to run social signals ingestion."""
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.social.ingest import SocialIngestor
from src.logging_config import get_logger

logger = get_logger(__name__)


def main():
    """Run social signals ingestion."""
    parser = argparse.ArgumentParser(
        description="Run social signals ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full ingestion
  python scripts/run_social_ingestion.py

  # Run with sandbox mode (mock data)
  python scripts/run_social_ingestion.py --sandbox

  # Limit posts for testing
  python scripts/run_social_ingestion.py --limit 10

  # Run in sandbox with limit
  python scripts/run_social_ingestion.py --sandbox --limit 5
        """,
    )
    
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Use sandbox mode with mock data (no real API calls)",
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of posts per source (for testing)",
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger("src").setLevel(logging.DEBUG)
    
    logger.info("=" * 60)
    logger.info("Social Signals Ingestion Pipeline")
    logger.info("=" * 60)
    
    if args.sandbox:
        logger.info("Running in SANDBOX mode (mock data)")
    
    if args.limit:
        logger.info(f"Limiting to {args.limit} posts per source")
    
    # Create ingestor
    ingestor = SocialIngestor(sandbox_mode=args.sandbox)
    
    # Run ingestion
    stats = ingestor.run_ingestion(limit=args.limit)
    
    # Print results
    logger.info("=" * 60)
    logger.info("Ingestion Results")
    logger.info("=" * 60)
    
    for key, value in stats.items():
        logger.info(f"{key}: {value}")
    
    # Exit with appropriate code
    if stats.get("status") == "completed":
        logger.info("✓ Ingestion completed successfully")
        sys.exit(0)
    elif stats.get("status") == "disabled":
        logger.warning("⚠ Social signals are disabled in config")
        sys.exit(0)
    else:
        logger.warning(f"⚠ Ingestion finished with status: {stats.get('status')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
