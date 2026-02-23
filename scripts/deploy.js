const hre = require("hardhat");
const fs = require('fs');
const path = require('path');

async function main() {
    console.log("🚀 Deploying PrescriptionStorage contract...\n");
    
    const PrescriptionStorage = await hre.ethers.getContractFactory("PrescriptionStorage");
    const prescriptionStorage = await PrescriptionStorage.deploy();
    await prescriptionStorage.waitForDeployment();
    
    const contractAddress = await prescriptionStorage.getAddress();
    console.log("✅ Contract deployed to:", contractAddress);
    
    // AUTO-UPDATE .env FILE
    const envPath = path.join(__dirname, '../.env');
    let envContent = fs.readFileSync(envPath, 'utf8');
    
    // Only update CONTRACT_ADDRESS (everything else stays same!)
    envContent = envContent.replace(
        /CONTRACT_ADDRESS=.*/,
        `CONTRACT_ADDRESS=${contractAddress}`
    );
    
    fs.writeFileSync(envPath, envContent);
    console.log("✅ .env CONTRACT_ADDRESS auto-updated!");
    
    // Save ABI for Django
    const artifactPath = path.join(
        __dirname,
        '../artifacts/contracts/PrescriptionStorage.sol/PrescriptionStorage.json'
    );
    const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));
    
    const djangoContractsPath = path.join(__dirname, '../apps/blockchain/contracts');
    if (!fs.existsSync(djangoContractsPath)) {
        fs.mkdirSync(djangoContractsPath, { recursive: true });
    }
    
    fs.writeFileSync(
        path.join(djangoContractsPath, 'PrescriptionStorage.json'),
        JSON.stringify(artifact, null, 2)
    );
    
    fs.writeFileSync(
        path.join(djangoContractsPath, 'contract-address.json'),
        JSON.stringify({
            address: contractAddress,
            network: "ganache",
            deployedAt: new Date().toISOString()
        }, null, 2)
    );
    
    console.log("\n🎉 DEPLOYMENT COMPLETE!");
    console.log(`📝 CONTRACT_ADDRESS=${contractAddress}`);
    console.log("✅ .env automatically updated - no manual changes needed!");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });