import os
from typing import Dict, List, Optional
from datetime import datetime
from supabase import create_client, Client

class Ledger:
    """
    Ledger to track agent ownership using Supabase
    """
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """
        Initialize ledger with Supabase
        
        Args:
            supabase_url: Supabase project URL (from env if not provided)
            supabase_key: Supabase anon key (from env if not provided)
        """
        supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        supabase_key = supabase_key or os.getenv("SUPABASE_ANON_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.table_name = "trades"
    
    def record_trade(self, agent_id: str, contract_ticker: str, 
                    quantity: int, side: str, trade_id: str, price: float,
                    payment_tx_hash: str = None):
        """
        Record a trade in the ledger
        
        Args:
            agent_id: Unique identifier for the agent
            contract_ticker: Contract ticker symbol
            quantity: Number of contracts
            side: "yes" or "no"
            trade_id: Kalshi order ID
            price: Price per contract
            payment_tx_hash: Optional payment transaction hash
        """
        try:
            trade_record = {
                "agent_id": agent_id,
                "contract_ticker": contract_ticker,
                "quantity": quantity,
                "side": side,
                "trade_id": trade_id,
                "price": float(price),
                "total_cost": float(price * quantity),
                "payment_tx_hash": payment_tx_hash
            }
            
            result = self.supabase.table(self.table_name).insert(trade_record).execute()
            
            if not result.data:
                raise Exception("Failed to insert trade record")
            
            return result.data[0]
        except Exception as e:
            print(f"Error recording trade: {e}")
            raise
    
    def get_agent_positions(self, agent_id: str) -> List[Dict]:
        """
        Get all positions for an agent
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            List of position dictionaries
        """
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("agent_id", agent_id)\
                .order("timestamp", desc=True)\
                .execute()
            
            # Transform to match old format
            positions = []
            for trade in result.data:
                positions.append({
                    "contract": trade["contract_ticker"],
                    "quantity": trade["quantity"],
                    "side": trade["side"],
                    "trade_id": trade["trade_id"],
                    "price": float(trade["price"]),
                    "timestamp": trade["timestamp"]
                })
            
            return positions
        except Exception as e:
            print(f"Error getting agent positions: {e}")
            return []
    
    def get_all_trades(self) -> List[Dict]:
        """Get all recorded trades"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .order("timestamp", desc=True)\
                .execute()
            
            return result.data or []
        except Exception as e:
            print(f"Error getting all trades: {e}")
            return []
    
    def get_agent_trades(self, agent_id: str) -> List[Dict]:
        """Get all trades for a specific agent"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("agent_id", agent_id)\
                .order("timestamp", desc=True)\
                .execute()
            
            return result.data or []
        except Exception as e:
            print(f"Error getting agent trades: {e}")
            return []
    
    def get_trade_by_id(self, trade_id: str) -> Optional[Dict]:
        """Get a specific trade by trade_id"""
        try:
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("trade_id", trade_id)\
                .single()\
                .execute()
            
            return result.data
        except Exception as e:
            print(f"Error getting trade by id: {e}")
            return None
