from flask import Flask, request, jsonify
from price_checker import KalshiPriceChecker
from trade_executor import KalshiTradeExecutor
from x402_handler import X402Handler
from ledger import Ledger
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Initialize components
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"  # Default to production/mainnet

# Use demo-specific keys if in demo mode, otherwise use production keys
if DEMO_MODE:
    kalshi_api_key = os.getenv("KALSHI_DEMO_API_KEY", os.getenv("KALSHI_API_KEY", ""))
    kalshi_private_key = os.getenv("KALSHI_DEMO_PRIVATE_KEY", os.getenv("KALSHI_PRIVATE_KEY", ""))
else:
    kalshi_api_key = os.getenv("KALSHI_API_KEY", "")
    kalshi_private_key = os.getenv("KALSHI_PRIVATE_KEY", "")

# Optional: Override base URL if needed (defaults to api.kalshi.com)
kalshi_base_url = os.getenv("KALSHI_BASE_URL")

# Price checking always uses production API (public market data)
# Trade execution uses demo/production based on DEMO_MODE and credentials
price_checker = KalshiPriceChecker(
    demo_mode=False, 
    base_url=os.getenv("KALSHI_PRICE_API_URL", "https://api.elections.kalshi.com")
)
trade_executor = KalshiTradeExecutor(
    api_key=kalshi_api_key,
    private_key_pem=kalshi_private_key,
    demo_mode=DEMO_MODE,
    base_url=kalshi_base_url  # Uses default: https://api.elections.kalshi.com
)
x402_handler = X402Handler(
    facilitator_url=os.getenv("X402_FACILITATOR_URL", "https://facilitator.p402.io"),
    recipient_address=os.getenv("X402_RECIPIENT_ADDRESS")
)
ledger = Ledger()

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "demo_mode": DEMO_MODE})

@app.route("/trade", methods=["POST"])
def execute_trade():
    """
    Main trade execution endpoint
    
    Flow:
    1. Get trade request (contract, quantity, side)
    2. Check current price from Kalshi
    3. Calculate required payment
    4. Check for payment signature
    5. If no payment: return HTTP 402
    6. If payment present: verify → execute trade → record in ledger
    
    Request body:
    {
        "contract": "CONTRACT-TICKER",
        "quantity": 10,
        "side": "yes"  // or "no"
    }
    
    Headers:
    - X-Agent-ID: Agent identifier
    - PAYMENT-SIGNATURE: Payment proof (on retry after 402)
    """
    data = request.json
    
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    
    # Validate request
    contract_ticker = data.get("contract")
    quantity = data.get("quantity")
    side = data.get("side")  # "yes" or "no"
    agent_id = request.headers.get("X-Agent-ID", "unknown")
    
    if not contract_ticker:
        return jsonify({"error": "Missing required field: contract"}), 400
    if not quantity or quantity <= 0:
        return jsonify({"error": "Missing or invalid field: quantity"}), 400
    if side not in ["yes", "no"]:
        return jsonify({"error": "Invalid side: must be 'yes' or 'no'"}), 400
    
    # Step 1: Get current price
    current_price = price_checker.get_current_price(contract_ticker, side)
    if current_price is None:
        return jsonify({
            "error": "Failed to get current price",
            "contract": contract_ticker
        }), 500
    
    # Step 2: Calculate required payment
    required_payment = current_price * quantity
    
    # Step 3: Check for payment signature
    payment_signature = request.headers.get("PAYMENT-SIGNATURE")
    
    if not payment_signature:
        # No payment yet - return 402
        memo = f"Kalshi trade: {contract_ticker} {side} x{quantity}"
        chain = os.getenv("X402_CHAIN", "ethereum")  # Default to ethereum
        return x402_handler.require_payment(
            amount_usd=required_payment,
            currency="USDC",
            recipient_address=os.getenv("X402_RECIPIENT_ADDRESS"),
            memo=memo,
            chain=chain
        )
    
    # Step 4: Verify payment
    recipient_address = os.getenv("X402_RECIPIENT_ADDRESS")
    chain = os.getenv("X402_CHAIN", "ethereum")
    if not x402_handler.verify_payment(payment_signature, required_payment, 
                                       currency="USDC", recipient_address=recipient_address,
                                       chain=chain):
        return jsonify({
            "error": "Payment verification failed",
            "required_amount": required_payment
        }), 402
    
    # Step 5: Execute trade
    trade_id = trade_executor.execute_trade(
        contract_ticker=contract_ticker,
        side=side,
        quantity=quantity,
        price=current_price
    )
    
    if not trade_id:
        return jsonify({
            "error": "Trade execution failed",
            "contract": contract_ticker
        }), 500
    
    # Step 6: Record in ledger
    payment_signature = request.headers.get("PAYMENT-SIGNATURE")
    ledger.record_trade(
        agent_id=agent_id,
        contract_ticker=contract_ticker,
        quantity=quantity,
        side=side,
        trade_id=trade_id,
        price=current_price,
        payment_tx_hash=payment_signature
    )
    
    return jsonify({
        "status": "success",
        "trade_id": trade_id,
        "price": current_price,
        "quantity": quantity,
        "contract": contract_ticker,
        "side": side,
        "total_cost": required_payment,
        "agent_id": agent_id
    })

@app.route("/price", methods=["GET"])
def get_price():
    """
    Get current price for a contract (no payment required)
    
    Query params:
    - contract: Contract ticker symbol (required)
    - side: "yes" or "no" (default: "yes")
    """
    contract_ticker = request.args.get("contract")
    side = request.args.get("side", "yes")
    
    if not contract_ticker:
        return jsonify({"error": "Missing required parameter: contract"}), 400
    
    if side not in ["yes", "no"]:
        return jsonify({"error": "Invalid side: must be 'yes' or 'no'"}), 400
    
    price = price_checker.get_current_price(contract_ticker, side)
    if price is None:
        return jsonify({
            "error": "Failed to get price",
            "contract": contract_ticker
        }), 500
    
    return jsonify({
        "contract": contract_ticker,
        "side": side,
        "price": price
    })

@app.route("/positions/<agent_id>", methods=["GET"])
def get_positions(agent_id):
    """Get all positions for an agent"""
    positions = ledger.get_agent_positions(agent_id)
    return jsonify({
        "agent_id": agent_id,
        "positions": positions,
        "count": len(positions)
    })

@app.route("/trades", methods=["GET"])
def get_trades():
    """Get all trades (optionally filtered by agent)"""
    agent_id = request.args.get("agent_id")
    
    if agent_id:
        trades = ledger.get_agent_trades(agent_id)
    else:
        trades = ledger.get_all_trades()
    
    return jsonify({
        "trades": trades,
        "count": len(trades)
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)

