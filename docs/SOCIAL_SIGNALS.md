# Social Signals & Sentiment Analysis Feature

**Status:** ✅ Implemented  
**Feature Toggle:** `ENABLE_SOCIAL_SIGNALS` (default: `False`)  
**Branch:** `feat/social-sentiment-20251117`

---

## Overview

This feature adds social media sentiment analysis and arbitrage detection to the Betting Expert Advisor system. It scrapes public social media posts and blog content about football matches, performs sentiment analysis, and combines those signals with bookmaker odds to produce suggested bets and detect arbitrage opportunities.

### Key Features

1. **Social Media Scraping** - Twitter/X, Reddit, blogs (respecting TOS and robots.txt)
2. **Sentiment Analysis** - VADER (fast) or HuggingFace transformers (accurate)
3. **Match Linking** - Fuzzy matching of posts to fixtures
4. **Sentiment Aggregation** - Rolling windows with recency weighting
5. **Arbitrage Detection** - Cross-bookmaker opportunity identification
6. **Suggested Bets** - AI-generated betting suggestions with confidence scores
7. **Virtual Bets** - Paper trading mode for testing suggestions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Social Signals Pipeline                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Scrapers (Twitter, Reddit, Blogs)                          │
│  - Rate limited, circuit breaker protected                  │
│  - Respects robots.txt and TOS                              │
│  - Caches results in Redis                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Match Linking (Fuzzy Matching)                             │
│  - Team name extraction                                     │
│  - Date/time window matching                                │
│  - Confidence scoring                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Sentiment Analysis (VADER / HuggingFace)                   │
│  - Score: -1.0 (negative) to +1.0 (positive)               │
│  - Label: positive, negative, neutral                       │
│  - Confidence: 0.0 to 1.0                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Aggregation (Per Match)                                    │
│  - Weighted by recency and author influence                 │
│  - Rolling time windows                                     │
│  - Statistical summaries                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Suggestion Generation                                       │
│  - Combines sentiment + odds + EV                           │
│  - Arbitrage detection                                      │
│  - Confidence scoring                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  API Endpoints & Dashboard                                   │
│  - /social/suggestions                                      │
│  - /social/arbitrage                                        │
│  - /social/match/{id}                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Tables

#### `social_posts`
Stores scraped social media posts and blog content.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| source | String(50) | twitter, reddit, blog |
| external_post_id | String(255) | Unique ID from source |
| author | String(255) | Post author |
| text | Text | Post content |
| created_at | DateTime | Post creation time |
| fetched_at | DateTime | When we scraped it |
| match_id | String(255) | Linked fixture ID |
| match_confidence | Float | Confidence of match link (0-1) |
| url | String(512) | Source URL |
| metadata | JSON | Additional data |

#### `social_sentiments`
Sentiment analysis results for posts.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| post_id | Integer | FK to social_posts |
| sentiment_score | Float | -1.0 to 1.0 |
| sentiment_label | String(20) | positive, negative, neutral |
| model | String(50) | vader, hf-distilbert |
| analyzed_at | DateTime | Analysis timestamp |
| confidence | Float | Model confidence |

#### `sentiment_aggregates`
Aggregated sentiment per match.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| match_id | String(255) | Fixture ID |
| aggregate_score | Float | Weighted average |
| positive_pct | Float | % positive posts |
| negative_pct | Float | % negative posts |
| neutral_pct | Float | % neutral posts |
| sample_count | Integer | Number of posts |
| window_start | DateTime | Time window start |
| window_end | DateTime | Time window end |
| created_at | DateTime | Aggregate timestamp |

#### `suggested_bets`
AI-generated betting suggestions.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| match_id | String(255) | Fixture ID |
| suggested_selection | String(255) | home, away, draw |
| suggested_odds | Float | Recommended odds |
| ev_score | Float | Expected value |
| sentiment_score | Float | Sentiment contribution |
| confidence | Float | Overall confidence (0-1) |
| is_arbitrage | Boolean | Arbitrage opportunity |
| arbitrage_legs | JSON | Arbitrage bet details |
| reason | Text | Human-readable explanation |
| source_json | JSON | Full source data |
| created_at | DateTime | Suggestion timestamp |
| expires_at | DateTime | Expiration time |
| is_executed | Boolean | Whether bet was placed |
| is_virtual | Boolean | Virtual/paper bet flag |

---

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Feature Toggle
ENABLE_SOCIAL_SIGNALS=False

# Scraping Configuration
SOCIAL_SCRAPE_SOURCES=twitter,reddit,blogs
SOCIAL_SCRAPE_INTERVAL_MINUTES=10
SOCIAL_DATA_RETENTION_DAYS=30
MAX_POSTS_PER_MATCH=200

# Sentiment Analysis
SENTIMENT_MODEL=vader  # or hf-distilbert

# Match Linking
MIN_MATCH_CONFIDENCE=0.6

# Arbitrage
ARBITRAGE_COMMISSION_RATE=0.02

# API Credentials (Optional)
TWITTER_BEARER_TOKEN=your_token_here
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=BettingAdvisorBot/0.1
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_SOCIAL_SIGNALS` | `False` | Master feature toggle |
| `SOCIAL_SCRAPE_SOURCES` | `twitter,reddit,blogs` | Comma-separated sources |
| `SOCIAL_SCRAPE_INTERVAL_MINUTES` | `10` | Scrape frequency |
| `SOCIAL_DATA_RETENTION_DAYS` | `30` | Data retention period |
| `SENTIMENT_MODEL` | `vader` | Sentiment model choice |
| `MIN_MATCH_CONFIDENCE` | `0.6` | Minimum match link confidence |
| `ARBITRAGE_COMMISSION_RATE` | `0.02` | Commission rate (2%) |
| `MAX_POSTS_PER_MATCH` | `200` | Max posts to analyze |

---

## API Endpoints

### GET /social/suggestions

Get AI-suggested bets based on sentiment and odds.

**Query Parameters:**
- `since` (optional): ISO datetime, filter suggestions after this time
- `limit` (optional): Max results (default: 20)
- `min_confidence` (optional): Minimum confidence threshold (default: 0.3)

**Response:**
```json
{
  "suggestions": [
    {
      "id": 123,
      "match_id": "soccer_epl_match_12345",
      "home_team": "Manchester United",
      "away_team": "Liverpool",
      "suggested_selection": "home",
      "suggested_odds": 2.10,
      "ev_score": 0.15,
      "sentiment_score": 0.65,
      "confidence": 0.78,
      "is_arbitrage": false,
      "reason": "Strong positive sentiment (65%) combined with favorable odds",
      "created_at": "2025-11-17T10:30:00Z",
      "expires_at": "2025-11-17T15:00:00Z"
    }
  ],
  "count": 1
}
```

### GET /social/arbitrage

Get active arbitrage opportunities.

**Response:**
```json
{
  "opportunities": [
    {
      "match_id": "soccer_epl_match_12345",
      "profit_margin": 3.5,
      "commission_adjusted_profit": 1.5,
      "total_stake": 100.0,
      "legs": [
        {
          "bookmaker": "Bet365",
          "selection": "home",
          "odds": 2.10,
          "stake": 47.62,
          "payout": 100.00
        },
        {
          "bookmaker": "Pinnacle",
          "selection": "away",
          "odds": 3.50,
          "stake": 28.57,
          "payout": 100.00
        },
        {
          "bookmaker": "Betfair",
          "selection": "draw",
          "odds": 4.20,
          "stake": 23.81,
          "payout": 100.00
        }
      ]
    }
  ],
  "count": 1
}
```

### GET /social/match/{match_id}

Get detailed sentiment and post samples for a match.

**Response:**
```json
{
  "match_id": "soccer_epl_match_12345",
  "aggregate": {
    "score": 0.45,
    "positive_pct": 65.0,
    "negative_pct": 20.0,
    "neutral_pct": 15.0,
    "sample_count": 150
  },
  "recent_posts": [
    {
      "source": "twitter",
      "author": "FootballFan123",
      "text": "Man Utd looking strong in training!",
      "sentiment_score": 0.72,
      "sentiment_label": "positive",
      "created_at": "2025-11-17T09:00:00Z"
    }
  ]
}
```

### POST /social/manual-bet

Create a manual bet (virtual or real).

**Request:**
```json
{
  "match_id": "soccer_epl_match_12345",
  "selection": "home",
  "stake": 50.0,
  "odds": 2.10,
  "is_virtual": true,
  "auto_execute": false
}
```

**Response:**
```json
{
  "bet_id": 456,
  "status": "created",
  "is_virtual": true,
  "message": "Virtual bet created successfully"
}
```

---

## Privacy & TOS Compliance

### Twitter/X
- **API:** Official Twitter API v2 (requires bearer token)
- **Rate Limits:** 500,000 tweets/month (free tier)
- **TOS:** Must comply with Twitter Developer Agreement
- **Implementation:** Uses `tweepy` library
- **Status:** ✅ Implemented with API key requirement

### Reddit
- **API:** Official Reddit API (requires client ID/secret)
- **Rate Limits:** 60 requests/minute
- **TOS:** Must comply with Reddit API Terms
- **Implementation:** Uses `praw` library
- **Status:** ✅ Implemented with API key requirement

### Blogs
- **Method:** RSS feeds + respectful HTML scraping
- **Rate Limits:** 1 request/second per domain
- **TOS:** Respects robots.txt
- **Implementation:** Uses `feedparser` + `BeautifulSoup`
- **Status:** ✅ Implemented with robots.txt checking

### Data Retention
- Posts older than `SOCIAL_DATA_RETENTION_DAYS` are automatically deleted
- PII is minimized (only public usernames stored)
- No authentication tokens stored in database

---

## Usage

### Enable the Feature

1. Update `.env`:
```bash
ENABLE_SOCIAL_SIGNALS=True
```

2. Run database migrations:
```bash
alembic upgrade head
```

3. Restart services:
```bash
docker-compose restart
```

### Test in Sandbox Mode

Run scraper with mock data (no API keys required):

```bash
python -m src.social.ingest --sandbox --limit 10
```

### View Suggestions

```bash
curl "http://localhost:5000/social/suggestions?limit=5&min_confidence=0.5"
```

### Check Arbitrage

```bash
curl "http://localhost:5000/social/arbitrage"
```

---

## Monitoring

### Prometheus Metrics

- `social_scrapes_total{source}` - Total scrapes by source
- `social_scrape_errors_total{source}` - Scrape errors by source
- `social_posts_in_db_total` - Total posts in database
- `sentiment_analysis_latency_seconds` - Analysis latency
- `suggested_bets_generated_total` - Total suggestions generated
- `arbitrage_opportunities_found_total` - Arbitrage opportunities

### Logs

All operations logged at INFO/ERROR levels:
- Scrape operations
- Sentiment analysis
- Match linking
- Suggestion generation
- API requests

---

## Migration

### Apply Migration

```bash
# Check current version
alembic current

# Apply social signals migration
alembic upgrade head

# Verify tables created
docker-compose exec db psql -U betting_user -d betting_advisor -c "\dt social_*"
```

### Rollback

```bash
# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>
```

---

## Testing

### Run Tests

```bash
# All social signals tests
pytest tests/social/ -v

# Specific module
pytest tests/social/test_sentiment.py -v

# With coverage
pytest tests/social/ --cov=src.social --cov-report=term
```

### Integration Test

```bash
# Run full pipeline with mock data
python -m src.social.ingest --sandbox --limit 10

# Check suggestions generated
curl "http://localhost:5000/social/suggestions"
```

---

## Troubleshooting

### Feature Not Working

1. Check feature toggle:
```bash
python -c "from src.config import settings; print(f'Enabled: {settings.ENABLE_SOCIAL_SIGNALS}')"
```

2. Check database tables:
```bash
docker-compose exec db psql -U betting_user -d betting_advisor -c "\dt social_*"
```

3. Check logs:
```bash
docker-compose logs monitoring | grep social
```

### No Suggestions Generated

1. Check if posts are being scraped:
```bash
curl "http://localhost:5000/social/match/soccer_epl_match_12345"
```

2. Check sentiment analysis:
```bash
python -c "from src.social.sentiment import analyze_text; print(analyze_text('Great match!'))"
```

3. Check match linking confidence:
```bash
# Lower MIN_MATCH_CONFIDENCE if needed
MIN_MATCH_CONFIDENCE=0.4
```

### API Credentials Issues

If you don't have API credentials:
1. Use sandbox mode: `--sandbox` flag
2. Disable specific sources: `SOCIAL_SCRAPE_SOURCES=blogs`
3. Use mock data for testing

---

## Future Enhancements

- [ ] Real-time streaming (Twitter Streaming API)
- [ ] Influencer weighting (verified accounts, follower count)
- [ ] Multi-language sentiment analysis
- [ ] Image/video sentiment analysis
- [ ] Historical sentiment trends
- [ ] Sentiment-based alerts
- [ ] Auto-execution of high-confidence suggestions
- [ ] Backtesting sentiment signals

---

## Support

For issues or questions:
- GitHub Issues: [github.com/yourusername/betting-expert-advisor/issues]
- Documentation: [docs/](docs/)
- Email: support@example.com

---

**Last Updated:** November 17, 2025  
**Version:** 1.0.0  
**Status:** ✅ Production Ready (Feature Toggle: OFF by default)
