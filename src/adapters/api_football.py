"""Adapter for API-Football via RapidAPI."""
from datetime import datetime
from typing import Dict, List, Optional
import requests
import pandas as pd

from src.config import settings
from src.data_fetcher import DataSourceInterface
from src.logging_config import get_logger

logger = get_logger(__name__)

class APIFootballAdapter(DataSourceInterface):
    """Data source adapter for API-Football via RapidAPI."""

    def __init__(self):
        """Initialize the API-Football adapter."""
        self.api_key = settings.RAPIDAPI_KEY
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
        
        if not self.api_key:
            logger.warning("RAPIDAPI_KEY not set. API-Football adapter will fail.")

        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        
        # Map our internal sport/league IDs to API-Football league IDs
        # These IDs might need to be looked up via their API first
        # For now, using common league IDs (Premier League = 39)
        self.league_map = {
            "soccer_epl": 39,
            "soccer_spain_la_liga": 140,
            "soccer_germany_bundesliga": 78,
            "soccer_italy_serie_a": 135,
            "soccer_france_ligue_one": 61,
            "soccer_uefa_champs_league": 2,
            "soccer_uefa_europa_league": 3
        }

    def fetch_fixtures(
        self, sport: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Fetch fixtures from API-Football."""
        if not self.api_key:
            logger.error("Cannot fetch fixtures: RAPIDAPI_KEY is missing")
            return pd.DataFrame()

        if sport not in self.league_map:
            logger.warning(f"Sport/League '{sport}' not supported by API-Football adapter yet.")
            return pd.DataFrame()

        league_id = self.league_map[sport]
        
        # API-Football requires 'season' (e.g., 2023)
        # Assuming current season is based on current year or start_date year
        # Better logic might be needed for cross-year seasons
        season = start_date.year if start_date else datetime.now().year
        # Adjust for leagues starting in late summer (e.g. 2023-2024 season is '2023')
        if datetime.now().month < 7:
             season -= 1

        params = {
            "league": league_id,
            "season": season,
        }
        
        if start_date and end_date:
            params["from"] = start_date.strftime("%Y-%m-%d")
            params["to"] = end_date.strftime("%Y-%m-%d")
        else:
             # Default to next 10 fixtures if no date provided
             params["next"] = 10

        try:
            url = f"{self.base_url}/fixtures"
            logger.info(f"Fetching fixtures from {url} with params: {params}")
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            fixtures = []
            for item in data.get("response", []):
                fixture = item["fixture"]
                teams = item["teams"]
                league = item["league"]
                
                # Normalize data structure to match our application's expectation
                fixtures.append({
                    "market_id": f"apifootball_{fixture['id']}",
                    "home": teams["home"]["name"],
                    "away": teams["away"]["name"],
                    "start": fixture["date"], # ISO 8601 string
                    "start_time": fixture["date"],
                    "league": league["name"],
                    "status": fixture["status"]["short"],
                    # Store odds if available directly? No, usually separate call or included.
                    # API-Football /fixtures response doesn't usually include odds unless requested?
                    # Actually, we need to call /odds endpoint separately usually, or use pre-match odds endpoint.
                })
                
            df = pd.DataFrame(fixtures)
            return df

        except Exception as e:
            logger.error(f"Error fetching fixtures from API-Football: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return pd.DataFrame()

    def fetch_odds(self, market_ids: List[str], markets: Optional[List[str]] = None) -> pd.DataFrame:
        """Fetch odds for specific fixtures and markets."""
        if not self.api_key:
             return pd.DataFrame()

        markets = markets or ["Match Winner", "Goals Over/Under", "Corner Kicks"]
        odds_data = []
        
        for market_id in market_ids:
            if not market_id.startswith("apifootball_"):
                continue
                
            fixture_id = market_id.replace("apifootball_", "")
            
            try:
                url = f"{self.base_url}/odds"
                params = {"fixture": fixture_id}
                
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    response_list = data.get("response", [])
                    
                    if response_list:
                         bookmakers = response_list[0].get("bookmakers", [])
                         bookie = next((b for b in bookmakers if b["name"] == "Bet365"), None)
                         if not bookie and bookmakers:
                             bookie = bookmakers[0]
                             
                         if bookie:
                             for bet in bookie.get("bets", []):
                                 bet_name = bet["name"]
                                 if bet_name in markets:
                                     for value in bet["values"]:
                                         selection = value["value"]
                                         
                                         # Normalize selection names and market types
                                         market_type = "h2h"
                                         if bet_name == "Goals Over/Under":
                                             market_type = "totals"
                                         elif bet_name == "Corner Kicks":
                                             market_type = "corners"
                                         
                                         # Normalize selection labels
                                         if selection == "Home": selection = "home"
                                         elif selection == "Away": selection = "away"
                                         elif selection == "Draw": selection = "draw"
                                         
                                         odds_data.append({
                                             "market_id": market_id,
                                             "market_type": market_type,
                                             "bet_name": bet_name,
                                             "selection": selection,
                                             "odds": float(value["odd"]),
                                             "source": f"API-Football ({bookie['name']})"
                                         })
            except Exception as e:
                logger.error(f"Error fetching odds for fixture {fixture_id}: {e}")
                continue
                
        return pd.DataFrame(odds_data)
