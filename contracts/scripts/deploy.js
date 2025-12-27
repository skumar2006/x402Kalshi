const { ethers } = require("hardhat");

async function main() {
    console.log("Deploying KalshiEscrow...");
    
    // Get network
    const network = await ethers.provider.getNetwork();
    console.log(`Network: ${network.name} (chainId: ${network.chainId})`);
    
    // Chain-specific USDC addresses
    const USDC_ADDRESSES = {
        1: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", // Ethereum mainnet
        8453: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", // Base mainnet
    };
    
    const USDC_ADDRESS = USDC_ADDRESSES[network.chainId] || USDC_ADDRESSES[1];
    const AUTHORIZED_RELEASER = process.env.EDGE_SERVICE_ADDRESS;
    const TIMEOUT_DURATION = 3600; // 1 hour
    
    if (!AUTHORIZED_RELEASER) {
        throw new Error("EDGE_SERVICE_ADDRESS environment variable is required");
    }
    
    console.log(`USDC Address: ${USDC_ADDRESS}`);
    console.log(`Authorized Releaser: ${AUTHORIZED_RELEASER}`);
    console.log(`Timeout Duration: ${TIMEOUT_DURATION} seconds`);
    
    const [deployer] = await ethers.getSigners();
    console.log(`Deploying with account: ${deployer.address}`);
    
    // Check balance
    const balance = await deployer.provider.getBalance(deployer.address);
    console.log(`Account balance: ${ethers.formatEther(balance)} ETH`);
    
    if (balance === 0n) {
        throw new Error("Deployer account has no ETH. Please fund the account.");
    }
    
    const KalshiEscrow = await ethers.getContractFactory("KalshiEscrow");
    
    // Get gas price
    const feeData = await deployer.provider.getFeeData();
    console.log(`Gas price: ${ethers.formatUnits(feeData.gasPrice || 0n, "gwei")} gwei`);
    
    // Deploy
    console.log("Deploying contract...");
    const escrow = await KalshiEscrow.deploy(
        USDC_ADDRESS,
        AUTHORIZED_RELEASER,
        TIMEOUT_DURATION,
        {
            gasLimit: 3000000
        }
    );
    
    console.log("Waiting for deployment...");
    await escrow.waitForDeployment();
    const address = await escrow.getAddress();
    
    console.log("\n✅ KalshiEscrow deployed successfully!");
    console.log(`Contract Address: ${address}`);
    console.log(`\nAdd to your .env file:`);
    console.log(`ESCROW_CONTRACT_ADDRESS=${address}`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });

