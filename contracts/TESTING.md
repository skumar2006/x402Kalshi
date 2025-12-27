# KalshiEscrow Smart Contract Testing Guide

This guide covers how to comprehensively test the KalshiEscrow smart contract to ensure everything is working as intended.

## Setup

### Install Dependencies
```bash
cd edge-service/contracts
npm install
```

### Compile Contracts
```bash
npm run compile
```

## Quick Start

### Run All Tests
```bash
npm test
```

### Run Tests with Verbose Output
```bash
npm run test:verbose
```

### Run Tests with Gas Reporting
```bash
npm run test:gas
```

### Generate Coverage Report
```bash
# First install coverage tool (optional)
npm install --save-dev solidity-coverage

# Then run coverage
npm run coverage
```

**Note**: Coverage reporting requires the `solidity-coverage` package. It's optional but recommended for comprehensive testing.

## Test Structure

The test suite (`test/KalshiEscrow.test.js`) covers:

### 1. **Deployment Tests**
- ✅ Correct initialization of USDC address, authorized releaser, timeout duration
- ✅ Owner assignment
- ✅ Validation of constructor parameters (rejects zero addresses, zero timeout)

### 2. **Owner Functions**
- ✅ Setting authorized releaser (owner only)
- ✅ Setting timeout duration (owner only)
- ✅ Access control (non-owners cannot modify settings)
- ✅ Input validation (rejects zero addresses/durations)

### 3. **Deposit Functionality**
- ✅ Successful deposits with correct state updates
- ✅ Deadline calculation (current time + timeout duration)
- ✅ USDC transfer from agent to contract
- ✅ Event emission
- ✅ Input validation (zero recipient, zero amount)
- ✅ Duplicate trade hash prevention
- ✅ Insufficient balance/allowance handling
- ✅ Multiple concurrent deposits

### 4. **Release Functionality**
- ✅ Authorized releaser can release funds
- ✅ Funds transferred to recipient
- ✅ State updates (released flag, kalshiTradeId)
- ✅ Access control (only authorized releaser)
- ✅ Prevents release of non-existent trades
- ✅ Prevents double release/refund
- ✅ Works after updating authorized releaser

### 5. **Refund Functionality**
- ✅ Authorized releaser can refund
- ✅ Agent can refund their own trade
- ✅ Anyone can refund after timeout
- ✅ Funds returned to agent
- ✅ State updates (refunded flag)
- ✅ Access control (unauthorized refunds before timeout)
- ✅ Prevents double refund/release
- ✅ Exact deadline handling

### 6. **Get Trade Function**
- ✅ Returns correct trade details
- ✅ Returns empty trade for non-existent hash
- ✅ Returns updated state after release

### 7. **Integration Scenarios**
- ✅ Complete flow: deposit → release
- ✅ Complete flow: deposit → refund
- ✅ Timeout refund scenario
- ✅ Multiple concurrent trades with different outcomes

### 8. **Edge Cases**
- ✅ Very small amounts (1 wei)
- ✅ Very large amounts (1M USDC)
- ✅ Empty kalshiTradeId string
- ✅ Long kalshiTradeId string

## Test Coverage

The test suite includes **100+ test cases** covering:
- ✅ All contract functions
- ✅ All access control mechanisms
- ✅ All state transitions
- ✅ All error conditions
- ✅ Edge cases and boundary conditions
- ✅ Integration scenarios

## Running Specific Tests

### Run a Specific Test File
```bash
npx hardhat test test/KalshiEscrow.test.js
```

### Run Tests Matching a Pattern
```bash
npx hardhat test --grep "Deposit"
npx hardhat test --grep "Release"
npx hardhat test --grep "Refund"
```

### Run a Specific Test Suite
```bash
npx hardhat test --grep "Deployment"
npx hardhat test --grep "Integration"
```

## Understanding Test Output

### Successful Test Run
```
  KalshiEscrow
    Deployment
      ✓ Should set the correct USDC address
      ✓ Should set the correct authorized releaser
      ...
    
    50 passing (X seconds)
```

### Failed Test
```
  1) KalshiEscrow
       Deposit
         Should allow agent to deposit USDC:
     Error: expected transaction to be reverted, but it didn't revert
```

## Manual Testing on Testnets

### 1. Deploy to a Testnet

```bash
# Set up .env file with:
# DEPLOYER_PRIVATE_KEY=your_testnet_private_key
# EDGE_SERVICE_ADDRESS=your_edge_service_address
# MAINNET_RPC_URL=your_rpc_url (or BASE_RPC_URL for Base)

npm run deploy:mainnet  # or deploy:base
```

### 2. Verify Contract on Etherscan/BaseScan
- Copy the deployed contract address
- Verify the contract source code
- Check the constructor parameters

### 3. Test Deposit Function
```javascript
// Using ethers.js or web3.js
const escrow = new ethers.Contract(escrowAddress, abi, signer);
const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("test-trade"));
const amount = ethers.parseUnits("100", 6); // 100 USDC

// Approve first
await usdc.approve(escrowAddress, amount);
// Then deposit
await escrow.depositWithAmount(recipientAddress, tradeHash, amount);
```

### 4. Test Release Function
```javascript
await escrow.connect(authorizedReleaser).release(tradeHash, "KALSHI-12345");
```

### 5. Test Refund Function
```javascript
// As authorized releaser
await escrow.connect(authorizedReleaser).refund(tradeHash);

// Or as agent
await escrow.connect(agent).refund(tradeHash);

// Or after timeout (anyone)
await escrow.connect(anyone).refund(tradeHash);
```

## Integration Testing with Edge Service

### 1. Deploy Contract to Testnet
```bash
npm run deploy:base  # or deploy:mainnet
```

### 2. Configure Edge Service
Set in `edge-service/.env`:
```
ESCROW_CONTRACT_ADDRESS=0x...
EDGE_SERVICE_PRIVATE_KEY=0x...
X402_CHAIN=base  # or ethereum
```

### 3. Test Full Flow
1. Start edge service: `python server.py`
2. Agent makes trade request
3. Edge service returns 402 with escrow address
4. Agent deposits to escrow
5. Agent retries with trade hash
6. Edge service verifies deposit
7. Edge service executes trade
8. Edge service releases escrow funds

### 4. Test Refund Flow
1. Agent deposits to escrow
2. Trade fails or timeout occurs
3. Edge service (or agent) calls refund
4. Funds returned to agent

## Security Testing Checklist

- [ ] ✅ Access control: Only owner can modify settings
- [ ] ✅ Access control: Only authorized releaser can release
- [ ] ✅ Access control: Agent or authorized releaser can refund before timeout
- [ ] ✅ Access control: Anyone can refund after timeout
- [ ] ✅ Reentrancy protection: No external calls before state updates
- [ ] ✅ Integer overflow/underflow: Using Solidity 0.8.20 (built-in checks)
- [ ] ✅ Input validation: All parameters validated
- [ ] ✅ State consistency: Cannot release and refund same trade
- [ ] ✅ Time manipulation: Deadline uses block.timestamp
- [ ] ✅ Front-running: Trade hash prevents duplicate deposits

## Gas Optimization Testing

Run tests with gas reporting:
```bash
npm run test:gas
```

Review gas costs for:
- Deposit operations
- Release operations
- Refund operations
- Owner functions

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Run Tests
  run: |
    cd edge-service/contracts
    npm install
    npm test
```

## Troubleshooting

### Tests Failing Locally
1. **Clear cache**: `npx hardhat clean`
2. **Recompile**: `npm run compile`
3. **Check Node version**: Requires Node.js 16+

### Gas Estimation Errors
- Ensure test accounts have sufficient balance
- Check network configuration in `hardhat.config.js`

### Time-based Tests Failing
- Tests use Hardhat's time manipulation helpers
- If tests are flaky, increase tolerance values

## Next Steps

1. ✅ Run full test suite: `npm test`
2. ✅ Review coverage report: `npm run coverage`
3. ✅ Deploy to testnet and verify
4. ✅ Test with edge service integration
5. ✅ Consider formal verification for critical paths
6. ✅ Get external audit before mainnet deployment

## Additional Resources

- [Hardhat Testing Documentation](https://hardhat.org/docs/writing-tests)
- [OpenZeppelin Contracts](https://docs.openzeppelin.com/contracts)
- [Ethers.js Documentation](https://docs.ethers.org/)

