// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title KalshiEscrow
 * @notice Escrow contract for x402 Kalshi trades
 * @dev Holds USDC in escrow until trade is confirmed or refunded
 */
contract KalshiEscrow is Ownable {
    IERC20 public usdc;
    address public authorizedReleaser;
    uint256 public timeoutDuration; // e.g., 3600 seconds (1 hour)
    
    struct Trade {
        address agent;
        address recipient;
        uint256 amount;
        string kalshiTradeId;
        uint256 deadline;
        bool released;
        bool refunded;
    }
    
    mapping(bytes32 => Trade) public trades;
    
    event Deposit(bytes32 indexed tradeHash, address indexed agent, address recipient, uint256 amount);
    event Released(bytes32 indexed tradeHash, string kalshiTradeId);
    event Refunded(bytes32 indexed tradeHash);
    
    constructor(address _usdc, address _authorizedReleaser, uint256 _timeoutDuration) Ownable(msg.sender) {
        require(_usdc != address(0), "Invalid USDC address");
        require(_authorizedReleaser != address(0), "Invalid releaser address");
        require(_timeoutDuration > 0, "Invalid timeout");
        
        usdc = IERC20(_usdc);
        authorizedReleaser = _authorizedReleaser;
        timeoutDuration = _timeoutDuration;
    }
    
    function setAuthorizedReleaser(address _releaser) external onlyOwner {
        require(_releaser != address(0), "Invalid address");
        authorizedReleaser = _releaser;
    }
    
    function setTimeoutDuration(uint256 _duration) external onlyOwner {
        require(_duration > 0, "Invalid duration");
        timeoutDuration = _duration;
    }
    
    /**
     * @notice Agent deposits USDC to escrow
     * @param recipient Address to receive funds after successful trade
     * @param tradeHash Unique hash identifying this trade
     * @param amount Amount of USDC (6 decimals)
     */
    function depositWithAmount(
        address recipient,
        bytes32 tradeHash,
        uint256 amount
    ) external {
        require(recipient != address(0), "Invalid recipient");
        require(amount > 0, "Amount must be > 0");
        require(trades[tradeHash].agent == address(0), "Trade exists");
        
        // Transfer USDC from agent to contract
        require(usdc.transferFrom(msg.sender, address(this), amount), "Transfer failed");
        
        trades[tradeHash] = Trade({
            agent: msg.sender,
            recipient: recipient,
            amount: amount,
            kalshiTradeId: "",
            deadline: block.timestamp + timeoutDuration,
            released: false,
            refunded: false
        });
        
        emit Deposit(tradeHash, msg.sender, recipient, amount);
    }
    
    /**
     * @notice Edge service releases funds after successful Kalshi trade
     * @param tradeHash Trade hash to release
     * @param kalshiTradeId Kalshi trade ID for transparency
     */
    function release(
        bytes32 tradeHash,
        string memory kalshiTradeId
    ) external {
        require(msg.sender == authorizedReleaser, "Unauthorized");
        Trade storage trade = trades[tradeHash];
        require(trade.agent != address(0), "Trade not found");
        require(!trade.released && !trade.refunded, "Already processed");
        
        trade.released = true;
        trade.kalshiTradeId = kalshiTradeId;
        
        require(usdc.transfer(trade.recipient, trade.amount), "Release failed");
        emit Released(tradeHash, kalshiTradeId);
    }
    
    /**
     * @notice Refund agent if trade fails or timeout
     * @param tradeHash Trade hash to refund
     */
    function refund(bytes32 tradeHash) external {
        Trade storage trade = trades[tradeHash];
        require(trade.agent != address(0), "Trade not found");
        require(!trade.released && !trade.refunded, "Already processed");
        require(
            msg.sender == authorizedReleaser || 
            msg.sender == trade.agent ||
            block.timestamp > trade.deadline,
            "Not authorized"
        );
        
        trade.refunded = true;
        require(usdc.transfer(trade.agent, trade.amount), "Refund failed");
        emit Refunded(tradeHash);
    }
    
    /**
     * @notice Get trade details
     * @param tradeHash Trade hash to query
     * @return Trade struct
     */
    function getTrade(bytes32 tradeHash) external view returns (Trade memory) {
        return trades[tradeHash];
    }
}

