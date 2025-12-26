from web3 import Web3
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chain_config import CHAIN_CONFIGS

class EscrowHandler:
    """
    Handles escrow contract interactions for edge service
    """
    def __init__(self, escrow_address: str, private_key: str, chain: str = "ethereum"):
        """
        Initialize escrow handler
        
        Args:
            escrow_address: Escrow contract address
            private_key: Private key for authorized releaser
            chain: Chain name
        """
        if chain not in CHAIN_CONFIGS:
            raise ValueError(f"Unsupported chain: {chain}")
        
        self.escrow_address = escrow_address
        self.chain = chain
        self.config = CHAIN_CONFIGS[chain]
        self.w3 = Web3(Web3.HTTPProvider(self.config["rpc_url"]))
        self.account = self.w3.eth.account.from_key(private_key)
        
        # Escrow contract ABI
        escrow_abi = [
            {
                "inputs": [{"name": "tradeHash", "type": "bytes32"}],
                "name": "getTrade",
                "outputs": [{
                    "components": [
                        {"name": "agent", "type": "address"},
                        {"name": "recipient", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                        {"name": "kalshiTradeId", "type": "string"},
                        {"name": "deadline", "type": "uint256"},
                        {"name": "released", "type": "bool"},
                        {"name": "refunded", "type": "bool"}
                    ],
                    "name": "",
                    "type": "tuple"
                }],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "tradeHash", "type": "bytes32"},
                    {"name": "kalshiTradeId", "type": "string"}
                ],
                "name": "release",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"name": "tradeHash", "type": "bytes32"}],
                "name": "refund",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        
        self.escrow_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(escrow_address),
            abi=escrow_abi
        )
    
    def verify_deposit(self, trade_hash: bytes) -> tuple[bool, dict]:
        """
        Check if deposit exists in escrow
        
        Args:
            trade_hash: Trade hash to check
        
        Returns:
            (exists, trade_info) tuple
        """
        try:
            trade = self.escrow_contract.functions.getTrade(trade_hash).call()
            agent_address = trade[0]
            recipient = trade[1]
            amount = trade[2]
            kalshi_trade_id = trade[3]
            deadline = trade[4]
            released = trade[5]
            refunded = trade[6]
            
            exists = agent_address != "0x0000000000000000000000000000000000000000"
            is_active = exists and not released and not refunded
            
            trade_info = {
                "agent": agent_address,
                "recipient": recipient,
                "amount": amount / 1_000_000,  # Convert to USD (6 decimals)
                "kalshi_trade_id": kalshi_trade_id,
                "deadline": deadline,
                "released": released,
                "refunded": refunded
            }
            
            return is_active, trade_info
        except Exception as e:
            print(f"Error verifying deposit: {e}")
            return False, {}
    
    def release_funds(self, trade_hash: bytes, kalshi_trade_id: str) -> str:
        """
        Release funds after successful trade
        
        Args:
            trade_hash: Trade hash
            kalshi_trade_id: Kalshi trade ID
        
        Returns:
            Transaction hash
        """
        try:
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            tx = self.escrow_contract.functions.release(trade_hash, kalshi_trade_id).build_transaction({
                'chainId': self.config["chain_id"],
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })
            
            signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            print(f"Released funds: {tx_hash.hex()}")
            return tx_hash.hex()
        except Exception as e:
            print(f"Error releasing funds: {e}")
            raise
    
    def refund_funds(self, trade_hash: bytes) -> str:
        """
        Refund if trade fails
        
        Args:
            trade_hash: Trade hash
        
        Returns:
            Transaction hash
        """
        try:
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            tx = self.escrow_contract.functions.refund(trade_hash).build_transaction({
                'chainId': self.config["chain_id"],
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })
            
            signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            print(f"Refunded funds: {tx_hash.hex()}")
            return tx_hash.hex()
        except Exception as e:
            print(f"Error refunding funds: {e}")
            raise

