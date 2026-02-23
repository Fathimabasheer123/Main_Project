# apps/blockchain/web3_manager.py

from web3 import Web3
from eth_account import Account
from django.conf import settings
import json
import os


class BlockchainManager:
    """Manage blockchain interactions"""
    
    def __init__(self):
        # Connect to blockchain
        self.w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_CONFIG['RPC_URL']))
        
        # Load account
        self.account = Account.from_key(settings.BLOCKCHAIN_CONFIG['PRIVATE_KEY'])
        self.w3.eth.default_account = self.account.address
        
        # Load contract
        contract_address = settings.BLOCKCHAIN_CONFIG['CONTRACT_ADDRESS']
        abi_path = os.path.join(
            settings.BASE_DIR, 'apps', 'blockchain',
            'contracts', 'PrescriptionStorage.json'
        )
        
        with open(abi_path, 'r') as f:
            contract_data = json.load(f)
            abi = contract_data['abi']
        
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi
        )
    
    def create_prescription(self, prescription_id, patient_address,
                          disease, drug, adverse_effects, ipfs_hash):
        """Store prescription on blockchain"""
        try:
            transaction = self.contract.functions.createPrescription(
                prescription_id,
                Web3.to_checksum_address(patient_address),
                disease,
                drug,
                adverse_effects,
                ipfs_hash
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': settings.BLOCKCHAIN_CONFIG['CHAIN_ID']
            })
            
            signed = self.w3.eth.account.sign_transaction(
                transaction, self.account.key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                'success': receipt['status'] == 1,
                'transaction_hash': tx_hash.hex(),
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_prescription(self, prescription_id):
        """Retrieve prescription from blockchain"""
        try:
            data = self.contract.functions.getPrescription(
                prescription_id
            ).call({'from': self.account.address})
            
            return {
                'success': True,
                'prescription': {
                    'id': data[0],
                    'patient': data[1],
                    'doctor': data[2],
                    'disease': data[3],
                    'drug': data[4],
                    'adverse_effects': data[5],
                    'ipfs_hash': data[6],
                    'timestamp': data[7],
                    'is_active': data[8],
                    'is_filled': data[9],
                    'status': data[10]
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def fill_prescription(self, prescription_id):
        """Mark prescription as filled"""
        try:
            transaction = self.contract.functions.fillPrescription(
                prescription_id
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': settings.BLOCKCHAIN_CONFIG['CHAIN_ID']
            })
            
            signed = self.w3.eth.account.sign_transaction(
                transaction, self.account.key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                'success': receipt['status'] == 1,
                'transaction_hash': tx_hash.hex(),
                'block_number': receipt['blockNumber']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ✅ LAZY INITIALIZATION - Only connects when first used!
# This prevents Django from crashing on startup
_manager = None

def get_blockchain_manager():
    global _manager
    if _manager is None:
        _manager = BlockchainManager()
    return _manager