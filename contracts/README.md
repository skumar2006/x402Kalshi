# Kalshi Escrow Contract

Smart contract for escrowing USDC payments until Kalshi trades are confirmed.

## Deployment

1. Install dependencies:
```bash
npm install
```

2. Set up environment variables in `.env`:
```bash
DEPLOYER_PRIVATE_KEY=0x...
EDGE_SERVICE_ADDRESS=0x...
```

3. Deploy to mainnet:
```bash
npm run deploy:mainnet
```

Or deploy to Base:
```bash
npm run deploy:base
```

4. Copy the deployed contract address to your `.env` files:
- `edge-service/.env`: `ESCROW_CONTRACT_ADDRESS=0x...`
- `agent/.env`: `ESCROW_CONTRACT_ADDRESS=0x...`

## Contract Functions

- `depositWithAmount(recipient, tradeHash, amount)`: Agent deposits USDC
- `release(tradeHash, kalshiTradeId)`: Edge service releases after successful trade
- `refund(tradeHash)`: Refund agent if trade fails or timeout

## Security

- Only authorized releaser (edge service) can release funds
- Agent or timeout can trigger refund
- 1 hour timeout by default (configurable)

