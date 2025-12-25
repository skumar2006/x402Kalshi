from flask import Response
from typing import Optional
import requests

class X402Handler:
    """
    Handles x402 payment protocol integration
    Uses facilitator for payment verification
    """
    def __init__(self, facilitator_url: str = "https://facilitator.p402.io", recipient_address: str = None):
        self.facilitator_url = facilitator_url
        self.recipient_address = recipient_address
    
    def require_payment(self, amount_usd: float, currency: str = "USDC", 
                       recipient_address: str = None, memo: str = "", 
                       chain: str = "ethereum") -> Response:
        """
        Returns HTTP 402 response with PAYMENT-REQUIRED header
        
        Format: PAYMENT-REQUIRED: amount=1.5;currency=USDC;address=0x...;chain=base;memo=...
        
        Args:
            amount_usd: Payment amount in USD
            currency: Currency code (default: USDC)
            recipient_address: x402 payment address (uses default if not provided)
            memo: Payment memo/description
            chain: Blockchain network (ethereum, base, polygon, arbitrum)
        
        Returns:
            Flask Response with 402 status and PAYMENT-REQUIRED header
        """
        address = recipient_address or self.recipient_address or "DEFAULT_X402_ADDRESS"
        
        # Format PAYMENT-REQUIRED header according to x402 spec
        payment_header = (
            f"amount={amount_usd};"
            f"currency={currency};"
            f"address={address};"
            f"chain={chain};"
            f"memo={memo}"
        )
        
        response = Response(
            status=402,
            headers={
                "PAYMENT-REQUIRED": payment_header,
                "Content-Type": "application/json"
            }
        )
        return response
    
    def verify_payment(self, payment_proof: str, expected_amount: float, 
                      currency: str = "USDC", recipient_address: str = None, 
                      chain: str = None) -> bool:
        """
        Verify payment using x402 facilitator or on-chain verification
        
        Args:
            payment_proof: Transaction hash from agent (hex string)
            expected_amount: Expected payment amount
            currency: Currency code
            recipient_address: Expected recipient address
            chain: Chain name (optional, will detect from transaction)
        
        Returns:
            True if payment verified, False otherwise
        """
        recipient = recipient_address or self.recipient_address
        
        try:
            # First try facilitator verification
            verify_url = f"{self.facilitator_url}/verify"
            
            payload = {
                "tx_hash": payment_proof,
                "expected_amount": expected_amount,
                "currency": currency,
                "recipient": recipient
            }
            if chain:
                payload["chain"] = chain
            
            response = requests.post(
                verify_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("verified", False)
            
            # If facilitator fails, try direct on-chain verification
            print(f"Facilitator returned status {response.status_code}, trying on-chain verification")
            return self._verify_on_chain(payment_proof, expected_amount, currency, recipient, chain)
            
        except requests.exceptions.RequestException as e:
            print(f"Error verifying payment with facilitator: {e}")
            # Fallback to on-chain verification
            return self._verify_on_chain(payment_proof, expected_amount, currency, recipient, chain)
        except Exception as e:
            print(f"Unexpected error in payment verification: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _verify_on_chain(self, tx_hash: str, expected_amount: float, 
                        currency: str, recipient_address: str, chain: str = None) -> bool:
        """
        Verify payment directly on-chain by checking transaction
        
        Args:
            tx_hash: Transaction hash
            expected_amount: Expected amount
            currency: Currency code
            recipient_address: Expected recipient
            chain: Chain name (optional, will detect from transaction if not provided)
        
        Returns:
            True if payment verified on-chain
        """
        try:
            from web3 import Web3
            import sys
            import os
            
            # Import chain configs
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from chain_config import CHAIN_CONFIGS
            
            # Ensure tx_hash has 0x prefix
            if not tx_hash.startswith('0x'):
                tx_hash = '0x' + tx_hash
            
            # Detect chain from transaction if not provided
            if not chain:
                # Try each chain to find the transaction
                for chain_name, config in CHAIN_CONFIGS.items():
                    try:
                        w3_test = Web3(Web3.HTTPProvider(config["rpc_url"]))
                        tx = w3_test.eth.get_transaction(tx_hash)
                        if tx:
                            chain = chain_name
                            print(f"Detected chain: {chain_name} (chain_id: {config['chain_id']})")
                            break
                    except:
                        continue
            
            # Default to ethereum if chain still not detected
            if not chain:
                chain = "ethereum"
                print(f"Could not detect chain, defaulting to {chain}")
            
            # Use chain-specific RPC
            config = CHAIN_CONFIGS.get(chain, CHAIN_CONFIGS["ethereum"])
            w3 = Web3(Web3.HTTPProvider(config["rpc_url"]))
            
            # First check if transaction exists (might be pending)
            try:
                tx = w3.eth.get_transaction(tx_hash)
                print(f"Transaction found: {tx_hash}")
            except Exception as e:
                print(f"Transaction not found: {e}")
                return False
            
            # Try to get receipt (will fail if not mined yet)
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
            except Exception as e:
                print(f"Transaction receipt not available yet (pending): {e}")
                # Transaction is pending - return False but don't treat as error
                return False
            
            if not receipt:
                print(f"Transaction {tx_hash} receipt is None")
                return False
                
            if receipt.status != 1:
                print(f"Transaction {tx_hash} failed (status: {receipt.status})")
                return False
            
            # Get transaction details
            tx = w3.eth.get_transaction(tx_hash)
            
            # Use chain-specific USDC address
            usdc_address = config["usdc_address"]
            if not tx.to or tx.to.lower() != usdc_address.lower():
                print(f"Transaction is not to USDC contract. To: {tx.to}, Expected: {usdc_address}")
                return False
            
            # Parse transfer event from logs
            transfer_abi = [{
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "from", "type": "address"},
                    {"indexed": True, "name": "to", "type": "address"},
                    {"indexed": False, "name": "value", "type": "uint256"}
                ],
                "name": "Transfer",
                "type": "event"
            }]
            
            usdc_contract = w3.eth.contract(
                address=Web3.to_checksum_address(usdc_address), 
                abi=transfer_abi
            )
            
            # Find Transfer event in logs
            recipient_lower = recipient_address.lower() if recipient_address else ""
            print(f"Looking for transfer to: {recipient_lower}")
            
            for log in receipt.logs:
                try:
                    # Check if this log is from USDC contract
                    if log.address.lower() != usdc_address.lower():
                        continue
                        
                    event = usdc_contract.events.Transfer().process_log(log)
                    to_address = event.args.to.lower()
                    amount_usdc = event.args.value / 1_000_000
                    
                    print(f"Found Transfer event: {amount_usdc} USDC to {to_address}")
                    
                    # Check if transfer is to recipient
                    if to_address == recipient_lower:
                        if abs(amount_usdc - expected_amount) < 0.01:  # Allow small rounding
                            print(f"Payment verified on-chain: {amount_usdc} USDC to {recipient_address}")
                            return True
                        else:
                            print(f"Amount mismatch: got {amount_usdc}, expected {expected_amount}")
                except Exception as e:
                    print(f"Error processing log: {e}")
                    continue
            
            print(f"Could not verify payment on-chain for tx {tx_hash}")
            return False
            
        except Exception as e:
            print(f"Error in on-chain verification: {e}")
            import traceback
            traceback.print_exc()
            return False

