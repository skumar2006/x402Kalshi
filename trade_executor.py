import requests
from typing import Optional
import json
import time
import hmac
import hashlib
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend

class KalshiTradeExecutor:
    """
    Executes trades on Kalshi using RSA-PSS signature authentication
    """
    def __init__(self, api_key: str, private_key_pem: str, demo_mode: bool = True, base_url: str = None):
        self.api_key = api_key
        self.demo_mode = demo_mode
        
        if base_url:
            self.base_url = base_url
        else:
            # Kalshi API base URL
            self.base_url = "https://api.elections.kalshi.com"
        
        self.api_version = "trade-api/v2"
        self.private_key = self._load_private_key(private_key_pem)
    
    def _load_private_key(self, private_key_pem: str):
        """Load RSA private key from PEM string"""
        try:
            # Handle PEM string - can be multi-line or single-line
            if isinstance(private_key_pem, str):
                # If it contains BEGIN/END markers, it's a proper PEM format
                if "BEGIN" in private_key_pem:
                    # Multi-line PEM string (from env with \n)
                    key_data = private_key_pem.replace('\\n', '\n').encode('utf-8')
                else:
                    # Try base64 decode if it's a single-line encoded key
                    try:
                        key_data = base64.b64decode(private_key_pem)
                    except:
                        # If base64 fails, treat as raw PEM
                        key_data = private_key_pem.encode('utf-8')
            else:
                key_data = private_key_pem
            
            return serialization.load_pem_private_key(
                key_data,
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            print(f"Error loading private key: {e}")
            raise
    
    def _sign_request(self, method: str, path: str, body: str = "") -> dict:
        """
        Create RSA-PSS signature for Kalshi API request
        Returns headers dict with authentication
        
        Kalshi API requires:
        - KALSHI-ACCESS-KEY: API Key ID
        - KALSHI-ACCESS-TIMESTAMP: Timestamp in milliseconds
        - KALSHI-ACCESS-SIGNATURE: Base64-encoded RSA-PSS signature
        """
        # Timestamp in MILLISECONDS (not seconds)
        timestamp = str(int(time.time() * 1000))
        
        # Create message to sign: timestamp + method + path (body excluded per Kalshi docs)
        # Some APIs exclude body from signature
        message = f"{timestamp}{method.upper()}{path}"
        
        # Debug logging
        print(f"DEBUG SIGNATURE:")
        print(f"  Timestamp: {timestamp}")
        print(f"  Method: {method.upper()}")
        print(f"  Path: {path}")
        print(f"  Body (not included): {body[:100]}..." if body else "  Body: (empty)")
        print(f"  Message to sign: {message}")
        
        # Sign with RSA-PSS
        signature = self.private_key.sign(
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Base64 encode signature
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # Correct Kalshi API header format
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature_b64,
            "Content-Type": "application/json"
        }
    
    def execute_trade(self, contract_ticker: str, side: str, quantity: int, price: float) -> Optional[str]:
        """
        Execute trade on Kalshi
        
        Args:
            contract_ticker: Contract ticker symbol
            side: "yes" or "no"
            quantity: Number of contracts to buy
            price: Price per contract (0-1)
        
        Returns:
            order_id or None if error
        """
        # Convert price to cents (Kalshi uses 0-100 scale)
        price_cents = int(price * 100)
        
        # Prepare order payload - use yes_price or no_price based on side
        order_data = {
            "ticker": contract_ticker,
            "side": side,  # "yes" or "no"
            "action": "buy",
            "count": quantity,
            "type": "limit"
        }
        
        # Add price based on side - use yes_price for "yes", no_price for "no"
        if side == "yes":
            order_data["yes_price"] = price_cents
        else:
            order_data["no_price"] = price_cents
        
        path = f"/{self.api_version}/portfolio/orders"
        body = json.dumps(order_data)
        
        try:
            headers = self._sign_request("POST", path, body)
            
            response = requests.post(
                f"{self.base_url}{path}",
                headers=headers,
                data=body,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract order ID from response
            # Adjust based on actual Kalshi API response structure
            if "order" in result:
                return result["order"].get("order_id")
            elif "order_id" in result:
                return result["order_id"]
            else:
                print(f"Unexpected response format: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error executing trade: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None
        except Exception as e:
            print(f"Unexpected error in trade execution: {e}")
            return None

