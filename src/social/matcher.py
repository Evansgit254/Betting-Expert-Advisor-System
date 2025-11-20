"""Match linking - fuzzy matching of posts to fixtures."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


def extract_team_names(text: str) -> List[str]:
    """Extract potential team names from text.

    Args:
        text: Text to analyze

    Returns:
        List of potential team names
    """
    # Common team name patterns
    common_teams = [
        "Manchester United", "Man United", "Man Utd", "MUFC",
        "Liverpool", "LFC",
        "Chelsea", "CFC",
        "Arsenal", "AFC",
        "Tottenham", "Spurs", "THFC",
        "Manchester City", "Man City", "MCFC",
        "Newcastle", "NUFC",
        "West Ham", "WHUFC",
        "Everton", "EFC",
        "Leicester", "LCFC",
        "Aston Villa", "AVFC",
        "Brighton",
        "Wolves", "Wolverhampton",
        "Crystal Palace", "CPFC",
        "Brentford",
        "Fulham", "FFC",
        "Bournemouth", "AFCB",
        "Nottingham Forest", "NFFC",
        "Luton", "LTFC",
        "Burnley", "BFC",
        "Sheffield United", "SUFC",
    ]

    found_teams = []
    text_lower = text.lower()

    for team in common_teams:
        if team.lower() in text_lower:
            found_teams.append(team)

    return found_teams


def fuzzy_match_team(team_name: str, candidate: str, threshold: float = 0.8) -> Tuple[bool, float]:
    """Fuzzy match team name against candidate.

    Args:
        team_name: Team name from fixture
        candidate: Candidate name from post
        threshold: Minimum similarity score (0-1)

    Returns:
        Tuple of (is_match, similarity_score)
    """
    try:
        from rapidfuzz import fuzz

        # Normalize
        team_lower = team_name.lower().strip()
        candidate_lower = candidate.lower().strip()

        # Exact match
        if team_lower == candidate_lower:
            return True, 1.0

        # Fuzzy match
        similarity = fuzz.ratio(team_lower, candidate_lower) / 100.0

        is_match = similarity >= threshold
        return is_match, similarity

    except ImportError:
        logger.error("rapidfuzz not installed. Install with: pip install rapidfuzz")
        # Fallback to simple substring match
        is_match = team_name.lower() in candidate.lower() or candidate.lower() in team_name.lower()
        return is_match, 1.0 if is_match else 0.0


def link_post_to_fixture(
    post: Dict, fixtures: List[Dict], time_window_hours: int = 48
) -> Optional[Tuple[str, float]]:
    """Link a post to a fixture using fuzzy matching.

    Args:
        post: Post dict with keys: text, created_at
        fixtures: List of fixture dicts with keys: id, home_team, away_team, commence_time
        time_window_hours: Time window for matching (hours before match)

    Returns:
        Tuple of (match_id, confidence) if match found, None otherwise
    """
    # Extract team names from post
    post_teams = extract_team_names(post["text"])

    if not post_teams:
        return None

    # Parse post time
    try:
        post_time = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
    except Exception:
        post_time = datetime.utcnow()

    best_match = None
    best_confidence = 0.0

    for fixture in fixtures:
        # Parse fixture time
        try:
            fixture_time = datetime.fromisoformat(fixture["commence_time"].replace("Z", "+00:00"))
        except Exception:
            continue

        # Check if post is within time window before match
        time_diff = (fixture_time - post_time).total_seconds() / 3600  # Hours
        if time_diff < 0 or time_diff > time_window_hours:
            continue

        # Check if any extracted team matches fixture teams
        home_team = fixture["home_team"]
        away_team = fixture["away_team"]

        for team in post_teams:
            # Check home team
            home_match, home_score = fuzzy_match_team(home_team, team)
            if home_match:
                confidence = home_score * 0.9  # Slight penalty for single team match
                if confidence > best_confidence:
                    best_match = fixture["id"]
                    best_confidence = confidence

            # Check away team
            away_match, away_score = fuzzy_match_team(away_team, team)
            if away_match:
                confidence = away_score * 0.9
                if confidence > best_confidence:
                    best_match = fixture["id"]
                    best_confidence = confidence

            # Bonus if both teams mentioned
            if home_match and away_match:
                confidence = min(home_score, away_score) * 1.0  # Full confidence
                if confidence > best_confidence:
                    best_match = fixture["id"]
                    best_confidence = confidence

    # Only return if confidence meets threshold
    if best_match and best_confidence >= settings.MIN_MATCH_CONFIDENCE:
        logger.debug(f"Linked post to {best_match} with confidence {best_confidence:.2f}")
        return best_match, best_confidence

    return None


def batch_link_posts(posts: List[Dict], fixtures: List[Dict]) -> List[Dict]:
    """Link multiple posts to fixtures.

    Args:
        posts: List of post dicts
        fixtures: List of fixture dicts

    Returns:
        List of posts with added keys: match_id, match_confidence
    """
    linked_posts = []

    for post in posts:
        result = link_post_to_fixture(post, fixtures)

        if result:
            match_id, confidence = result
            post["match_id"] = match_id
            post["match_confidence"] = confidence
            linked_posts.append(post)
        else:
            # Keep post but mark as unlinked
            post["match_id"] = None
            post["match_confidence"] = 0.0
            linked_posts.append(post)

    linked_count = sum(1 for p in linked_posts if p["match_id"])
    logger.info(f"Linked {linked_count}/{len(posts)} posts to fixtures")

    return linked_posts
