// scripts/deploy.js
const hre = require("hardhat");
const fs = require('fs');
const path = require('path');

async function main() {
    console.log("🚀 Deploying PrescriptionStorage...\n");

    // Get deployer account
    const [deployer] = await hre.ethers.getSigners();
    console.log("📝 Deploying with account:", deployer.address);

    const balance = await hre.ethers.provider.getBalance(
        deployer.address
    );
    console.log(
        "💰 Account balance:",
        hre.ethers.formatEther(balance), "ETH\n"
    );

    // Deploy contract
    const PrescriptionStorage = await hre.ethers.getContractFactory(
        "PrescriptionStorage"
    );
    const contract = await PrescriptionStorage.deploy();

    // FIX 1 - Updated syntax for ethers v6
    await contract.waitForDeployment();
    const contractAddress = await contract.getAddress();

    console.log("✅ Contract deployed to:", contractAddress);

    // FIX 2 - Register deployer as doctor for testing
    // (Remove this in production)
    if (hre.network.name !== 'mainnet') {
        console.log("\n🔧 Registering deployer as doctor for testing...");
        const tx = await contract.registerDoctor(deployer.address);
        await tx.wait();
        console.log("✅ Deployer registered as doctor");

        // Also register as pharmacy for testing
        const tx2 = await contract.registerPharmacy(deployer.address);
        await tx2.wait();
        console.log("✅ Deployer registered as pharmacy");
    }

    // FIX 3 - Save contract data with deployer address
    const contractData = {
        address: contractAddress,
        network: hre.network.name,
        chainId: hre.network.config.chainId || 1337,
        deployedAt: new Date().toISOString(),
        deployedBy: deployer.address  // ← Answer to your question
    };

    // Save paths
    const djangoContractsPath = path.join(
        __dirname, '../apps/blockchain/contracts'
    );

    if (!fs.existsSync(djangoContractsPath)) {
        fs.mkdirSync(djangoContractsPath, { recursive: true });
    }

    // Get artifact
    const artifactPath = path.join(
        __dirname,
        '../artifacts/contracts/PrescriptionStorage.sol/PrescriptionStorage.json'
    );
    const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));

    // Save ABI
    fs.writeFileSync(
        path.join(djangoContractsPath, 'PrescriptionStorage.json'),
        JSON.stringify(artifact, null, 2)
    );

    // Save contract address
    fs.writeFileSync(
        path.join(djangoContractsPath, 'contract-address.json'),
        JSON.stringify(contractData, null, 2)
    );

    // FIX 4 - Show .env update instructions
    console.log("\n📋 Update your .env file:");
    console.log(`CONTRACT_ADDRESS=${contractAddress}`);
    console.log(`# Deployer: ${deployer.address}`);
    console.log("\n✅ Deployment complete!");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("❌ Deployment failed:", error);
        process.exit(1);
    });