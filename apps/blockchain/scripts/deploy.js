const hre = require("hardhat");
const fs = require('fs');
const path = require('path');

async function main() {
    console.log("🚀 Deploying PrescriptionStorage contract...\n");
    
    const PrescriptionStorage = await hre.ethers.getContractFactory("PrescriptionStorage");
    const prescriptionStorage = await PrescriptionStorage.deploy();
    
    await prescriptionStorage.deployed();
    
    console.log("✅ PrescriptionStorage deployed to:", prescriptionStorage.address);
    
    // Save contract address and ABI to Django app
    const contractData = {
        address: prescriptionStorage.address,
        network: hre.network.name,
        deployedAt: new Date().toISOString()
    };
    
    // Get the compiled contract
    const artifactPath = path.join(__dirname, '../artifacts/contracts/PrescriptionStorage.sol/PrescriptionStorage.json');
    const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));
    
    // Save to Django blockchain app
    const djangoContractsPath = path.join(__dirname, '../apps/blockchain/contracts');
    
    // Create directory if it doesn't exist
    if (!fs.existsSync(djangoContractsPath)) {
        fs.mkdirSync(djangoContractsPath, { recursive: true });
    }
    
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
    
    console.log("\n✅ Contract ABI saved to: apps/blockchain/contracts/PrescriptionStorage.json");
    console.log("✅ Contract address saved to: apps/blockchain/contracts/contract-address.json");
    
    console.log("\n📝 Update your .env file with:");
    console.log(`CONTRACT_ADDRESS=${prescriptionStorage.address}`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });