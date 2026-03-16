// scripts/deploy.js
const hre = require("hardhat");
const fs  = require('fs');
const path = require('path');

async function main() {
    console.log("🚀 Deploying PrescriptionStorage contract...\n");

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
    await contract.waitForDeployment();

    const contractAddress = await contract.getAddress();
    console.log("✅ Contract deployed to:", contractAddress);

    // ======== AUTO REGISTER BACKEND WALLET ========
    // Backend wallet MUST be registered as both
    // doctor and pharmacy to send transactions

    const tx1 = await contract.registerDoctor(deployer.address);
    await tx1.wait();
    console.log(
        "✅ Backend registered as doctor:", deployer.address
    );

    const tx2 = await contract.registerPharmacy(deployer.address);
    await tx2.wait();
    console.log(
        "✅ Backend registered as pharmacy:", deployer.address
    );

    // ======== REGISTER KNOWN DOCTOR WALLETS ========
    // Add doctor wallet addresses here
    // These are the personal wallets doctors set in profile

    const knownDoctors = [
        '0xc11F37381B2b3e7e4ee6afa72441726e3c052ee1', // deepthi
        // Add more doctor wallets here as needed
    ];

    for (const wallet of knownDoctors) {
        try {
            const tx = await contract.registerDoctor(wallet);
            await tx.wait();
            console.log("✅ Doctor wallet registered:", wallet);
        } catch (e) {
            console.log("⚠️  Doctor already registered:", wallet);
        }
    }

    // ======== REGISTER KNOWN PHARMACY WALLETS ========
    // Add pharmacy wallet addresses here after they register
    // and set their wallet in settings

    const knownPharmacies = [
        // Add pharmacy wallet here after registration
        // '0xPHARMACY_WALLET_HERE', // priypharm
    ];

    for (const wallet of knownPharmacies) {
        try {
            const tx = await contract.registerPharmacy(wallet);
            await tx.wait();
            console.log("✅ Pharmacy wallet registered:", wallet);
        } catch (e) {
            console.log("⚠️  Pharmacy already registered:", wallet);
        }
    }

    // ======== AUTO UPDATE .env ========
    const envPath = path.join(__dirname, '../.env');
    let envContent = fs.readFileSync(envPath, 'utf8');

    envContent = envContent.replace(
        /CONTRACT_ADDRESS=.*/,
        `CONTRACT_ADDRESS=${contractAddress}`
    );

    fs.writeFileSync(envPath, envContent);
    console.log("\n✅ .env CONTRACT_ADDRESS auto-updated!");

    // ======== SAVE ABI FOR DJANGO ========
    const artifactPath = path.join(
        __dirname,
        '../artifacts/contracts/PrescriptionStorage.sol/PrescriptionStorage.json'
    );
    const artifact = JSON.parse(
        fs.readFileSync(artifactPath, 'utf8')
    );

    const djangoContractsPath = path.join(
        __dirname, '../apps/blockchain/contracts'
    );
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
            address:    contractAddress,
            network:    'ganache',
            deployedBy: deployer.address,
            deployedAt: new Date().toISOString()
        }, null, 2)
    );

    // ======== SUMMARY ========
    console.log("\n🎉 DEPLOYMENT COMPLETE!");
    console.log(`📝 CONTRACT_ADDRESS=${contractAddress}`);
    console.log(`👤 DEPLOYER=${deployer.address}`);
    console.log("✅ .env automatically updated!");
    console.log(
        "✅ Backend wallet auto-registered as doctor + pharmacy!"
    );
    console.log("\n📌 NOTE: When new doctor/pharmacy sets wallet");
    console.log(
        "   in profile → auto-registered via Django signal."
    );
    console.log(
        "   No manual shell commands needed!"
    );
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("❌ Deployment failed:", error);
        process.exit(1);
    });
