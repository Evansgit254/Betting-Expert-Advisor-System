
import json
import requests
from typing import Any, Dict, Optional
from datetime import datetime, timedelta, timezone

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)

class BetfairAdapter:
    """Adapter for Betfair Exchange API."""

    def __init__(self):
        self.app_key = settings.BETFAIR_APP_KEY
        self.session_token = settings.BETFAIR_SESSION_TOKEN
        self.base_url = settings.BETFAIR_API_BASE
        
        if not self.app_key or not self.session_token:
            logger.warning("Betfair credentials missing. Live betting will fail.")

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        return {
            "X-Application": self.app_key,
            "X-Authentication": self.session_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _post(self, endpoint: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to Betfair API."""
        url = f"{self.base_url}/exchange/betting/rest/v1.0/{method}/"
        
        try:
            response = requests.post(
                url,
                json=params,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Betfair API error {response.status_code}: {response.text}")
                raise Exception(f"Betfair API error: {response.status_code}")
                
            return response.json()
            
        except Exception as e:
            logger.error(f"Betfair request failed: {e}")
            raise

    def find_market(self, home_team: str, away_team: str, event_time: Optional[datetime] = None) -> Optional[str]:
        """Find Betfair market ID for a given match."""
        # 1. Search for events
        filter_params = {
            "textQuery": f"{home_team} {away_team}",
            "eventTypeIds": ["1"],  # Soccer
        }
        
        if event_time:
            filter_params["marketStartTime"] = {
                "from": (event_time - timedelta(hours=2)).isoformat(),
                "to": (event_time + timedelta(hours=2)).isoformat()
            }

        try:
            # listEvents to find the event ID
            # Note: This is a simplified search. Robust search requires fuzzy matching.
            # For now, we assume the text query works reasonably well.
            # Ideally we should use listMarketCatalogue directly with text query.
            
            params = {
                "filter": filter_params,
                "maxResults": 1,
                "marketProjection": ["MARKET_START_TIME", "EVENT"]
            }
            
            # We actually want listMarketCatalogue to get the market ID directly
            # But listMarketCatalogue textQuery searches market name, not event name usually.
            # Let's try searching for the Match Odds market specifically.
            
            params = {
                "filter": {
                    "textQuery": f"{home_team} v {away_team}", # Betfair uses 'v' convention often
                    "eventTypeIds": ["1"],
                    "marketTypeCodes": ["MATCH_ODDS"]
                },
                "maxResults": 1,
                "marketProjection": ["RUNNER_METADATA"]
            }
            
            result = self._post("betting", "listMarketCatalogue", params)
            
            if result and len(result) > 0:
                market_id = result[0].get("marketId")
                logger.info(f"Resolved Betfair market ID: {market_id} for {home_team} v {away_team}")
                return market_id
                
            logger.warning(f"Could not find Betfair market for {home_team} v {away_team}")
            return None

        except Exception as e:
            logger.error(f"Error finding market: {e}")
            return None

    def place_bet(
        self,
        market_id: str,
        selection: str,
        stake: float,
        odds: float,
        idempotency_key: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Place a bet on Betfair.
        
        Args:
            market_id: Betfair Market ID (must start with '1.')
            selection: 'home', 'away', or 'draw' (or specific runner name)
            stake: Amount to bet
            odds: Decimal odds
            idempotency_key: Unique key for deduplication
            **kwargs: Must contain 'home_team' and 'away_team' if selection is generic
        """
        
        # 1. Resolve Market ID
        if not market_id.startswith("1."):
            logger.error(f"Invalid Betfair Market ID: {market_id}. Must start with '1.'.")
            raise ValueError("Cannot place bet: Invalid Betfair Market ID")

        # 2. Resolve Selection ID
        selection_id = None
        
        try:
            # Fetch market details to get runners
            market_details = self._post("betting", "listMarketCatalogue", {
                "filter": {"marketIds": [market_id]},
                "maxResults": 1,
                "marketProjection": ["RUNNER_DESCRIPTION", "EVENT"]
            })
            
            if not market_details:
                raise ValueError(f"Market {market_id} not found on Betfair")
                
            runners = market_details[0].get("runners", [])
            
            # Strategy 1: Direct Name Match (if selection is a team name)
            for runner in runners:
                if runner["runnerName"].lower() == selection.lower():
                    selection_id = runner["selectionId"]
                    break
            
            # Strategy 2: Home/Away/Draw Mapping (if selection is generic)
            if not selection_id and selection.lower() in ["home", "away", "draw"]:
                # We need team names to map 'home'/'away'
                home_team = kwargs.get("home_team")
                away_team = kwargs.get("away_team")
                
                if not home_team or not away_team:
                    # Try to get from event details if available
                    event = market_details[0].get("event", {})
                    event_name = event.get("name", "")
                    if " v " in event_name:
                        parts = event_name.split(" v ")
                        home_team = parts[0].strip()
                        away_team = parts[1].strip()
                
                if home_team and away_team:
                    target_name = None
                    if selection.lower() == "home":
                        target_name = home_team
                    elif selection.lower() == "away":
                        target_name = away_team
                    elif selection.lower() == "draw":
                        target_name = "The Draw" # Betfair standard
                    
                    # Fuzzy match runner names
                    for runner in runners:
                        r_name = runner["runnerName"].lower()
                        t_name = target_name.lower() if target_name else ""
                        
                        # Exact match or containment
                        if r_name == t_name or t_name in r_name or r_name in t_name:
                            selection_id = runner["selectionId"]
                            break
                            
            if not selection_id:
                raise ValueError(f"Could not map selection '{selection}' to a Betfair Selection ID")

            # 3. Construct Payload
            payload = {
                "marketId": market_id,
                "instructions": [
                    {
                        "selectionId": selection_id,
                        "handicap": 0,
                        "side": "BACK",
                        "orderType": "LIMIT",
                        "limitOrder": {
                            "size": str(stake),
                            "price": str(odds),
                            "persistenceType": "LAPSE"
                        }
                    }
                ]
            }
            
            if idempotency_key:
                payload["customerRef"] = idempotency_key

            logger.info(f"Placing Betfair order: {payload}")
            return self._post("betting", "placeOrders", payload)

        except Exception as e:
            logger.error(f"Failed to place Betfair bet: {e}")
            raise
