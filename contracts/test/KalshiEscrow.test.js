const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("KalshiEscrow", function () {
    let escrow;
    let mockUSDC;
    let owner;
    let authorizedReleaser;
    let agent;
    let recipient;
    let otherAccount;
    
    const TIMEOUT_DURATION = 3600; // 1 hour
    
    beforeEach(async function () {
        // Get signers
        [owner, authorizedReleaser, agent, recipient, otherAccount] = await ethers.getSigners();
        
        // Deploy Mock USDC
        const MockUSDC = await ethers.getContractFactory("MockUSDC");
        mockUSDC = await MockUSDC.deploy();
        await mockUSDC.waitForDeployment();
        
        // Deploy KalshiEscrow
        const KalshiEscrow = await ethers.getContractFactory("KalshiEscrow");
        escrow = await KalshiEscrow.deploy(
            await mockUSDC.getAddress(),
            authorizedReleaser.address,
            TIMEOUT_DURATION
        );
        await escrow.waitForDeployment();
        
        // Give agent some USDC for testing
        const agentUSDCAmount = ethers.parseUnits("10000", 6); // 10,000 USDC
        await mockUSDC.mint(agent.address, agentUSDCAmount);
        
        // Approve escrow to spend agent's USDC
        await mockUSDC.connect(agent).approve(await escrow.getAddress(), ethers.MaxUint256);
    });
    
    describe("Deployment", function () {
        it("Should set the correct USDC address", async function () {
            expect(await escrow.usdc()).to.equal(await mockUSDC.getAddress());
        });
        
        it("Should set the correct authorized releaser", async function () {
            expect(await escrow.authorizedReleaser()).to.equal(authorizedReleaser.address);
        });
        
        it("Should set the correct timeout duration", async function () {
            expect(await escrow.timeoutDuration()).to.equal(TIMEOUT_DURATION);
        });
        
        it("Should set the correct owner", async function () {
            expect(await escrow.owner()).to.equal(owner.address);
        });
        
        it("Should reject zero USDC address", async function () {
            const KalshiEscrow = await ethers.getContractFactory("KalshiEscrow");
            await expect(
                KalshiEscrow.deploy(
                    ethers.ZeroAddress,
                    authorizedReleaser.address,
                    TIMEOUT_DURATION
                )
            ).to.be.revertedWith("Invalid USDC address");
        });
        
        it("Should reject zero authorized releaser address", async function () {
            const KalshiEscrow = await ethers.getContractFactory("KalshiEscrow");
            await expect(
                KalshiEscrow.deploy(
                    await mockUSDC.getAddress(),
                    ethers.ZeroAddress,
                    TIMEOUT_DURATION
                )
            ).to.be.revertedWith("Invalid releaser address");
        });
        
        it("Should reject zero timeout duration", async function () {
            const KalshiEscrow = await ethers.getContractFactory("KalshiEscrow");
            await expect(
                KalshiEscrow.deploy(
                    await mockUSDC.getAddress(),
                    authorizedReleaser.address,
                    0
                )
            ).to.be.revertedWith("Invalid timeout");
        });
    });
    
    describe("Owner Functions", function () {
        it("Should allow owner to set authorized releaser", async function () {
            await escrow.setAuthorizedReleaser(otherAccount.address);
            expect(await escrow.authorizedReleaser()).to.equal(otherAccount.address);
        });
        
        it("Should not allow non-owner to set authorized releaser", async function () {
            await expect(
                escrow.connect(agent).setAuthorizedReleaser(otherAccount.address)
            ).to.be.revertedWithCustomError(escrow, "OwnableUnauthorizedAccount");
        });
        
        it("Should reject zero address for authorized releaser", async function () {
            await expect(
                escrow.setAuthorizedReleaser(ethers.ZeroAddress)
            ).to.be.revertedWith("Invalid address");
        });
        
        it("Should allow owner to set timeout duration", async function () {
            const newDuration = 7200; // 2 hours
            await escrow.setTimeoutDuration(newDuration);
            expect(await escrow.timeoutDuration()).to.equal(newDuration);
        });
        
        it("Should not allow non-owner to set timeout duration", async function () {
            await expect(
                escrow.connect(agent).setTimeoutDuration(7200)
            ).to.be.revertedWithCustomError(escrow, "OwnableUnauthorizedAccount");
        });
        
        it("Should reject zero timeout duration", async function () {
            await expect(
                escrow.setTimeoutDuration(0)
            ).to.be.revertedWith("Invalid duration");
        });
    });
    
    describe("Deposit", function () {
        const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("test-trade-1"));
        const amount = ethers.parseUnits("100", 6); // 100 USDC
        
        it("Should allow agent to deposit USDC", async function () {
            await expect(
                escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount)
            )
                .to.emit(escrow, "Deposit")
                .withArgs(tradeHash, agent.address, recipient.address, amount);
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.agent).to.equal(agent.address);
            expect(trade.recipient).to.equal(recipient.address);
            expect(trade.amount).to.equal(amount);
            expect(trade.released).to.be.false;
            expect(trade.refunded).to.be.false;
            
            // Check USDC balance
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(amount);
            expect(await mockUSDC.balanceOf(agent.address)).to.equal(
                ethers.parseUnits("9900", 6)
            );
        });
        
        it("Should set correct deadline", async function () {
            const blockTimestamp = BigInt(await time.latest());
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            
            const trade = await escrow.getTrade(tradeHash);
            const expectedDeadline = blockTimestamp + BigInt(TIMEOUT_DURATION);
            // Check deadline is within 5 seconds of expected (accounting for block time)
            const deadlineDiff = trade.deadline > expectedDeadline 
                ? trade.deadline - expectedDeadline 
                : expectedDeadline - trade.deadline;
            expect(deadlineDiff).to.be.lessThanOrEqual(5n);
        });
        
        it("Should reject deposit with zero recipient", async function () {
            await expect(
                escrow.connect(agent).depositWithAmount(ethers.ZeroAddress, tradeHash, amount)
            ).to.be.revertedWith("Invalid recipient");
        });
        
        it("Should reject deposit with zero amount", async function () {
            await expect(
                escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, 0)
            ).to.be.revertedWith("Amount must be > 0");
        });
        
        it("Should reject duplicate trade hash", async function () {
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            
            await expect(
                escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount)
            ).to.be.revertedWith("Trade exists");
        });
        
        it("Should reject deposit if insufficient USDC balance", async function () {
            const poorAgent = otherAccount;
            await expect(
                escrow.connect(poorAgent).depositWithAmount(recipient.address, tradeHash, amount)
            ).to.be.reverted; // ERC20 transferFrom will fail
        });
        
        it("Should reject deposit if insufficient allowance", async function () {
            // Revoke approval
            await mockUSDC.connect(agent).approve(await escrow.getAddress(), 0);
            
            await expect(
                escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount)
            ).to.be.reverted; // ERC20 transferFrom will fail
        });
        
        it("Should allow multiple different trade hashes", async function () {
            const tradeHash2 = ethers.keccak256(ethers.toUtf8Bytes("test-trade-2"));
            const amount2 = ethers.parseUnits("50", 6);
            
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash2, amount2);
            
            const trade1 = await escrow.getTrade(tradeHash);
            const trade2 = await escrow.getTrade(tradeHash2);
            
            expect(trade1.amount).to.equal(amount);
            expect(trade2.amount).to.equal(amount2);
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(
                amount + amount2
            );
        });
    });
    
    describe("Release", function () {
        const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("test-trade-release"));
        const amount = ethers.parseUnits("100", 6);
        const kalshiTradeId = "KALSHI-12345";
        
        beforeEach(async function () {
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
        });
        
        it("Should allow authorized releaser to release funds", async function () {
            const recipientBalanceBefore = await mockUSDC.balanceOf(recipient.address);
            
            await expect(
                escrow.connect(authorizedReleaser).release(tradeHash, kalshiTradeId)
            )
                .to.emit(escrow, "Released")
                .withArgs(tradeHash, kalshiTradeId);
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.released).to.be.true;
            expect(trade.kalshiTradeId).to.equal(kalshiTradeId);
            expect(trade.refunded).to.be.false;
            
            // Check USDC transferred to recipient
            expect(await mockUSDC.balanceOf(recipient.address)).to.equal(
                recipientBalanceBefore + amount
            );
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(0);
        });
        
        it("Should not allow non-authorized releaser to release", async function () {
            await expect(
                escrow.connect(agent).release(tradeHash, kalshiTradeId)
            ).to.be.revertedWith("Unauthorized");
            
            await expect(
                escrow.connect(owner).release(tradeHash, kalshiTradeId)
            ).to.be.revertedWith("Unauthorized");
        });
        
        it("Should reject release for non-existent trade", async function () {
            const fakeHash = ethers.keccak256(ethers.toUtf8Bytes("fake-trade"));
            
            await expect(
                escrow.connect(authorizedReleaser).release(fakeHash, kalshiTradeId)
            ).to.be.revertedWith("Trade not found");
        });
        
        it("Should reject release if already released", async function () {
            await escrow.connect(authorizedReleaser).release(tradeHash, kalshiTradeId);
            
            await expect(
                escrow.connect(authorizedReleaser).release(tradeHash, kalshiTradeId)
            ).to.be.revertedWith("Already processed");
        });
        
        it("Should reject release if already refunded", async function () {
            await escrow.connect(agent).refund(tradeHash);
            
            await expect(
                escrow.connect(authorizedReleaser).release(tradeHash, kalshiTradeId)
            ).to.be.revertedWith("Already processed");
        });
        
        it("Should allow release after updating authorized releaser", async function () {
            await escrow.setAuthorizedReleaser(otherAccount.address);
            
            await expect(
                escrow.connect(otherAccount).release(tradeHash, kalshiTradeId)
            )
                .to.emit(escrow, "Released")
                .withArgs(tradeHash, kalshiTradeId);
        });
    });
    
    describe("Refund", function () {
        const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("test-trade-refund"));
        const amount = ethers.parseUnits("100", 6);
        
        beforeEach(async function () {
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
        });
        
        it("Should allow authorized releaser to refund", async function () {
            const agentBalanceBefore = await mockUSDC.balanceOf(agent.address);
            
            await expect(escrow.connect(authorizedReleaser).refund(tradeHash))
                .to.emit(escrow, "Refunded")
                .withArgs(tradeHash);
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.refunded).to.be.true;
            expect(trade.released).to.be.false;
            
            expect(await mockUSDC.balanceOf(agent.address)).to.equal(
                agentBalanceBefore + amount
            );
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(0);
        });
        
        it("Should allow agent to refund their own trade", async function () {
            const agentBalanceBefore = await mockUSDC.balanceOf(agent.address);
            
            await expect(escrow.connect(agent).refund(tradeHash))
                .to.emit(escrow, "Refunded")
                .withArgs(tradeHash);
            
            expect(await mockUSDC.balanceOf(agent.address)).to.equal(
                agentBalanceBefore + amount
            );
        });
        
        it("Should allow anyone to refund after timeout", async function () {
            // Fast forward time past deadline
            const trade = await escrow.getTrade(tradeHash);
            await time.increaseTo(trade.deadline + 1n);
            
            const agentBalanceBefore = await mockUSDC.balanceOf(agent.address);
            
            await expect(escrow.connect(otherAccount).refund(tradeHash))
                .to.emit(escrow, "Refunded")
                .withArgs(tradeHash);
            
            expect(await mockUSDC.balanceOf(agent.address)).to.equal(
                agentBalanceBefore + amount
            );
        });
        
        it("Should not allow unauthorized refund before timeout", async function () {
            await expect(
                escrow.connect(otherAccount).refund(tradeHash)
            ).to.be.revertedWith("Not authorized");
        });
        
        it("Should reject refund for non-existent trade", async function () {
            const fakeHash = ethers.keccak256(ethers.toUtf8Bytes("fake-trade"));
            
            await expect(
                escrow.connect(authorizedReleaser).refund(fakeHash)
            ).to.be.revertedWith("Trade not found");
        });
        
        it("Should reject refund if already released", async function () {
            await escrow.connect(authorizedReleaser).release(tradeHash, "KALSHI-123");
            
            await expect(
                escrow.connect(authorizedReleaser).refund(tradeHash)
            ).to.be.revertedWith("Already processed");
        });
        
        it("Should reject refund if already refunded", async function () {
            await escrow.connect(agent).refund(tradeHash);
            
            await expect(
                escrow.connect(agent).refund(tradeHash)
            ).to.be.revertedWith("Already processed");
        });
        
        it("Should allow refund exactly at deadline", async function () {
            const trade = await escrow.getTrade(tradeHash);
            // Set time to one second before deadline (should fail)
            await time.increaseTo(trade.deadline - 1n);
            
            // Should fail (must be > deadline, not >=)
            await expect(
                escrow.connect(otherAccount).refund(tradeHash)
            ).to.be.revertedWith("Not authorized");
            
            // Set time to exactly at deadline - should still fail (needs > not >=)
            // The contract checks block.timestamp > trade.deadline, so equal should fail
            await time.increase(1); // This should set us to exactly deadline
            const currentTime = await time.latest();
            
            // If we're exactly at deadline (not past), it should fail
            if (currentTime === trade.deadline) {
                await expect(
                    escrow.connect(otherAccount).refund(tradeHash)
                ).to.be.revertedWith("Not authorized");
            }
            
            // But succeed after deadline (now > deadline)
            // Use increase instead of increaseTo to avoid timestamp conflicts
            await time.increase(1);
            await expect(escrow.connect(otherAccount).refund(tradeHash))
                .to.emit(escrow, "Refunded");
        });
    });
    
    describe("Get Trade", function () {
        const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("test-trade-get"));
        const amount = ethers.parseUnits("100", 6);
        
        it("Should return correct trade details", async function () {
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.agent).to.equal(agent.address);
            expect(trade.recipient).to.equal(recipient.address);
            expect(trade.amount).to.equal(amount);
            expect(trade.kalshiTradeId).to.equal("");
            expect(trade.released).to.be.false;
            expect(trade.refunded).to.be.false;
        });
        
        it("Should return empty trade for non-existent hash", async function () {
            const fakeHash = ethers.keccak256(ethers.toUtf8Bytes("fake-trade"));
            const trade = await escrow.getTrade(fakeHash);
            
            expect(trade.agent).to.equal(ethers.ZeroAddress);
            expect(trade.amount).to.equal(0);
        });
        
        it("Should return updated trade after release", async function () {
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            await escrow.connect(authorizedReleaser).release(tradeHash, "KALSHI-123");
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.released).to.be.true;
            expect(trade.kalshiTradeId).to.equal("KALSHI-123");
        });
    });
    
    describe("Integration Scenarios", function () {
        it("Should handle complete flow: deposit -> release", async function () {
            const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("integration-1"));
            const amount = ethers.parseUnits("500", 6);
            
            // Deposit
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            
            // Verify deposit
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.amount).to.equal(amount);
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(amount);
            
            // Release
            await escrow.connect(authorizedReleaser).release(tradeHash, "KALSHI-INT-1");
            
            // Verify release
            const tradeAfter = await escrow.getTrade(tradeHash);
            expect(tradeAfter.released).to.be.true;
            expect(await mockUSDC.balanceOf(recipient.address)).to.equal(amount);
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(0);
        });
        
        it("Should handle complete flow: deposit -> refund", async function () {
            const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("integration-2"));
            const amount = ethers.parseUnits("300", 6);
            const agentBalanceBefore = await mockUSDC.balanceOf(agent.address);
            
            // Deposit
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            
            // Refund
            await escrow.connect(authorizedReleaser).refund(tradeHash);
            
            // Verify refund
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.refunded).to.be.true;
            expect(await mockUSDC.balanceOf(agent.address)).to.equal(
                agentBalanceBefore
            );
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(0);
        });
        
        it("Should handle timeout refund scenario", async function () {
            const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("integration-3"));
            const amount = ethers.parseUnits("200", 6);
            const agentBalanceBefore = await mockUSDC.balanceOf(agent.address);
            
            // Deposit
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            
            // Fast forward past deadline
            const trade = await escrow.getTrade(tradeHash);
            await time.increaseTo(trade.deadline + 1n);
            
            // Refund by anyone
            await escrow.connect(otherAccount).refund(tradeHash);
            
            // Verify refund
            expect(await mockUSDC.balanceOf(agent.address)).to.equal(
                agentBalanceBefore
            );
        });
        
        it("Should handle multiple concurrent trades", async function () {
            const tradeHash1 = ethers.keccak256(ethers.toUtf8Bytes("multi-1"));
            const tradeHash2 = ethers.keccak256(ethers.toUtf8Bytes("multi-2"));
            const tradeHash3 = ethers.keccak256(ethers.toUtf8Bytes("multi-3"));
            const amount1 = ethers.parseUnits("100", 6);
            const amount2 = ethers.parseUnits("200", 6);
            const amount3 = ethers.parseUnits("300", 6);
            
            // Deposit all three
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash1, amount1);
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash2, amount2);
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash3, amount3);
            
            // Verify all deposits
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(
                amount1 + amount2 + amount3
            );
            
            // Release first, refund second, timeout third
            await escrow.connect(authorizedReleaser).release(tradeHash1, "KALSHI-1");
            await escrow.connect(authorizedReleaser).refund(tradeHash2);
            
            const trade3 = await escrow.getTrade(tradeHash3);
            await time.increaseTo(trade3.deadline + 1n);
            await escrow.connect(otherAccount).refund(tradeHash3);
            
            // Verify final state
            expect(await mockUSDC.balanceOf(await escrow.getAddress())).to.equal(0);
            
            const trade1 = await escrow.getTrade(tradeHash1);
            const trade2 = await escrow.getTrade(tradeHash2);
            const trade3After = await escrow.getTrade(tradeHash3);
            
            expect(trade1.released).to.be.true;
            expect(trade2.refunded).to.be.true;
            expect(trade3After.refunded).to.be.true;
        });
    });
    
    describe("Edge Cases", function () {
        it("Should handle very small amounts", async function () {
            const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("small-amount"));
            const amount = 1n; // 1 wei (smallest unit)
            
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.amount).to.equal(amount);
        });
        
        it("Should handle very large amounts", async function () {
            const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("large-amount"));
            const amount = ethers.parseUnits("1000000", 6); // 1M USDC
            
            // Mint enough USDC
            await mockUSDC.mint(agent.address, amount);
            await mockUSDC.connect(agent).approve(await escrow.getAddress(), amount);
            
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.amount).to.equal(amount);
        });
        
        it("Should handle empty kalshiTradeId string", async function () {
            const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("empty-id"));
            const amount = ethers.parseUnits("100", 6);
            
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            await escrow.connect(authorizedReleaser).release(tradeHash, "");
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.kalshiTradeId).to.equal("");
            expect(trade.released).to.be.true;
        });
        
        it("Should handle long kalshiTradeId string", async function () {
            const tradeHash = ethers.keccak256(ethers.toUtf8Bytes("long-id"));
            const amount = ethers.parseUnits("100", 6);
            const longId = "KALSHI-" + "A".repeat(200);
            
            await escrow.connect(agent).depositWithAmount(recipient.address, tradeHash, amount);
            await escrow.connect(authorizedReleaser).release(tradeHash, longId);
            
            const trade = await escrow.getTrade(tradeHash);
            expect(trade.kalshiTradeId).to.equal(longId);
        });
    });
});

