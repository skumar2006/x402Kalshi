import requests
from typing import Optional

class KalshiPriceChecker:
    """
    Fetches current market prices from Kalshi API
    Uses public endpoints - no authentication required for market data
    """
    def __init__(self, demo_mode: bool = True, base_url: str = None):
        if base_url:
            self.base_url = base_url
        else:
            # Kalshi API base URL
            self.base_url = "https://api.elections.kalshi.com"
        self.api_version = "trade-api/v2"
        # Base URL for API calls (without version prefix for some endpoints)
        self.api_base = f"{self.base_url}/{self.api_version}"
    
    def get_current_price(self, contract_ticker: str, side: str = "yes") -> Optional[float]:
        """
        Get current best price for buying 'yes' or 'no' on a contract
        
        Args:
            contract_ticker: The contract ticker symbol (e.g., "EXAMPLE-TICKER")
            side: "yes" or "no"
        
        Returns:
            price (0-1) representing the cost per share, or None if error
        """
        # Query Kalshi market data endpoint
        # Correct format: GET /trade-api/v2/markets/{ticker}
        url = f"{self.api_base}/markets/{contract_ticker}"
        
        try:
            response = requests.get(url, timeout=10)
            print(f"DEBUG: Price check URL: {url}, Status: {response.status_code}")
            if response.status_code != 200:
                print(f"DEBUG: Response: {response.text[:500]}")
            response.raise_for_status()
            data = response.json()
            
            # Extract price from market data
            # Kalshi API returns: { "market": { "yes_ask": 54, "yes_bid": 52, "no_ask": 48, "no_bid": 46, ... } }
            # Prices are in cents (0-100), convert to 0-1
            # Use "ask" price (what you pay to buy), not "bid" (what you get to sell)
            
            if "market" not in data:
                print(f"DEBUG: No 'market' key in response. Keys: {list(data.keys())}")
                return None
            
            market = data["market"]
            
            if side == "yes":
                # Get yes_ask (what you pay to buy yes) - prefer ask over bid
                if "yes_ask" in market:
                    price_cents = float(market["yes_ask"])
                    return price_cents / 100.0
                elif "yes_bid" in market:
                    price_cents = float(market["yes_bid"])
                    return price_cents / 100.0
                elif "yes_ask_dollars" in market:
                    # Already in decimal format
                    return float(market["yes_ask_dollars"])
                elif "last_price" in market:
                    # Fallback to last price
                    price_cents = float(market["last_price"])
                    return price_cents / 100.0
            else:
                # Get no_ask (what you pay to buy no)
                if "no_ask" in market:
                    price_cents = float(market["no_ask"])
                    return price_cents / 100.0
                elif "no_bid" in market:
                    price_cents = float(market["no_bid"])
                    return price_cents / 100.0
                elif "no_ask_dollars" in market:
                    # Already in decimal format
                    return float(market["no_ask_dollars"])
                elif "last_price" in market:
                    # Fallback to last price
                    price_cents = float(market["last_price"])
                    return price_cents / 100.0
            
            print(f"DEBUG: Could not find price in market data. Keys: {list(market.keys())}")
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching price: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"DEBUG: Error response: {e.response.status_code} - {e.response.text[:500]}")
            return None
        except Exception as e:
            print(f"Error parsing price data: {e}")
            import traceback
            traceback.print_exc()
            return None
    

