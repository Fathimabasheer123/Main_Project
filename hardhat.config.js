require("@nomicfoundation/hardhat-toolbox");
require('dotenv').config();

module.exports = {
  solidity: {
    version: "0.8.19",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  
  networks: {
    // FIX 1 - Hardhat built-in node
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337
    },
    
    // FIX 2 - Ganache GUI (default port 7545)
    ganache: {
      url: "http://127.0.0.1:8545",
      chainId: 1337,
      accounts: process.env.PRIVATE_KEY 
        ? [`0x${process.env.PRIVATE_KEY.replace('0x', '')}`] 
        : [],
    },
    
    // FIX 3 - Ganache CLI (port 8545)
    ganache_cli: {
      url: "http://127.0.0.1:8545",
      chainId: 1337,
      accounts: process.env.PRIVATE_KEY
        ? [`0x${process.env.PRIVATE_KEY.replace('0x', '')}`]
        : [],
    }
  },
  
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  }
};