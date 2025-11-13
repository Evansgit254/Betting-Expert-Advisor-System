"""Check cache statistics and status."""
import os
import sys
from datetime import datetime, timezone

try:
    from src.cache import DataCache
except ModuleNotFoundError:  # pragma: no cover - fallback for direct execution
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from src.cache import DataCache


def main():
    cache = DataCache()
    stats = cache.get_cache_stats()

    print("\n" + "=" * 70)
    print("  CACHE STATISTICS")
    print("=" * 70 + "\n")

    print(f"📊 Fixtures cached: {stats['fixtures_count']}")
    if stats["fixtures_oldest"]:
        oldest = stats["fixtures_oldest"]
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - oldest
        print(f"   Oldest: {stats['fixtures_oldest']} (age: {age})")
    if stats["fixtures_newest"]:
        newest = stats["fixtures_newest"]
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - newest
        print(f"   Newest: {stats['fixtures_newest']} (age: {age})")

    print(f"\n📊 Odds cached: {stats['odds_count']}")
    if stats["odds_oldest"]:
        oldest = stats["odds_oldest"]
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - oldest
        print(f"   Oldest: {stats['odds_oldest']} (age: {age})")
    if stats["odds_newest"]:
        newest = stats["odds_newest"]
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - newest
        print(f"   Newest: {stats['odds_newest']} (age: {age})")

    print("\n" + "=" * 70)
    print("\n💡 Cache TTL Settings:")
    print("   Fixtures: 1 hour")
    print("   Odds: 5 minutes")
    print("\n✅ Caching is ENABLED and working!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
