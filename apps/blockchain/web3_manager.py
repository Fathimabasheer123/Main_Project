# apps/blockchain/web3_manager.py
from web3 import Web3
from eth_account import Account
from django.conf import settings
import json
import os
import threading
import hashlib


class BlockchainManager:

    def __init__(self):
        rpc_url = settings.BLOCKCHAIN_CONFIG['RPC_URL']
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(
                f"Cannot connect to blockchain at {rpc_url}. "
                f"Make sure Ganache is running."
            )

        # Step 1 — Set account FIRST
        private_key = settings.BLOCKCHAIN_CONFIG['PRIVATE_KEY']
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        self.account = Account.from_key(private_key)
        self.w3.eth.default_account = self.account.address

        # Step 2 — Load contract address
        contract_address = settings.BLOCKCHAIN_CONFIG['CONTRACT_ADDRESS']

        # Step 3 — Load ABI from artifacts
        abi_path = os.path.join(
            settings.BASE_DIR, 'artifacts', 'contracts',
            'PrescriptionStorage.sol', 'PrescriptionStorage.json'
        )

        if not os.path.exists(abi_path):
            raise FileNotFoundError(
                'ABI not found. Run: npx hardhat compile'
            )

        with open(abi_path, 'r') as f:
            contract_data = json.load(f)

        abi = contract_data['abi']

        # Step 4 — Verify ABI has required functions
        fn_names = [
            item['name'] for item in abi
            if item.get('type') == 'function'
        ]
        print('web3_manager ABI functions:', fn_names)

        if 'isDoctor' not in fn_names:
            raise ValueError(
                'ABI missing isDoctor. '
                'Run: npx hardhat compile then redeploy.'
            )

        # Step 5 — Initialize contract
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi
        )

        # Step 6 — Initialize nonce
        self._nonce_lock = threading.Lock()
        self._current_nonce = self.w3.eth.get_transaction_count(
            self.account.address
        )

    # ==================== HELPERS ====================

    def _get_next_nonce(self):
        with self._nonce_lock:
            chain_nonce = self.w3.eth.get_transaction_count(
                self.account.address
            )
            nonce = max(chain_nonce, self._current_nonce)
            self._current_nonce = nonce + 1
            return nonce

    def _estimate_gas(self, fn):
        try:
            return int(
                fn.estimate_gas({'from': self.account.address}) * 1.2
            )
        except Exception:
            return 500000

    def _reset_nonce(self):
        self._current_nonce = self.w3.eth.get_transaction_count(
            self.account.address
        )

    @staticmethod
    def make_data_hash(prescription_data: dict) -> bytes:
        sorted_json = json.dumps(prescription_data, sort_keys=True)
        hex_hash = hashlib.sha256(
            sorted_json.encode('utf-8')
        ).hexdigest()
        return bytes.fromhex(hex_hash)

    # ==================== CORE FUNCTIONS ====================

    def create_prescription(
        self,
        prescription_id: str,
        patient_address: str,
        data_hash: bytes,
        ipfs_hash: str = ""
    ) -> dict:
        try:
            if not Web3.is_address(patient_address):
                return {
                    'success': False,
                    'error': 'Invalid patient wallet address'
                }

            if not isinstance(data_hash, bytes) or len(data_hash) != 32:
                return {
                    'success': False,
                    'error': 'data_hash must be 32 bytes (SHA-256)'
                }

            # Check not already exists
            existing = self.contract.functions.prescriptions(
                prescription_id
            ).call()
            if existing[5] != 0:
                return {
                    'success': False,
                    'error': 'Prescription ID already exists on blockchain'
                }

            fn = self.contract.functions.createPrescription(
                prescription_id,
                Web3.to_checksum_address(patient_address),
                data_hash,
                ipfs_hash
            )

            tx = fn.build_transaction({
                'from':     self.account.address,
                'nonce':    self._get_next_nonce(),
                'gas':      self._estimate_gas(fn),
                'gasPrice': self.w3.eth.gas_price,
                'chainId':  settings.BLOCKCHAIN_CONFIG['CHAIN_ID']
            })

            signed  = self.w3.eth.account.sign_transaction(
                tx, self.account.key
            )
            tx_hash = self.w3.eth.send_raw_transaction(
                signed.raw_transaction
            )
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120
            )

            return {
                'success':          receipt['status'] == 1,
                'transaction_hash': tx_hash.hex(),
                'block_number':     receipt['blockNumber'],
                'gas_used':         receipt['gasUsed'],
                'data_hash':        data_hash.hex()
            }

        except Exception as e:
            self._reset_nonce()
            return {'success': False, 'error': str(e)}

    def verify_prescription(
        self,
        prescription_id: str,
        prescription_data: dict
    ) -> dict:
        try:
            current_hash = self.make_data_hash(prescription_data)

            is_valid, is_active, is_expired, is_filled = \
                self.contract.functions.verifyPrescription(
                    prescription_id,
                    current_hash
                ).call()

            return {
                'success':      True,
                'is_valid':     is_valid,
                'is_active':    is_active,
                'is_expired':   is_expired,
                'is_filled':    is_filled,
                'tampered':     not is_valid,
                'current_hash': current_hash.hex()
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_prescription(
        self,
        prescription_id: str,
        caller_address: str = None
    ) -> dict:
        try:
            call_from = self.account.address
            if caller_address and Web3.is_address(caller_address):
                call_from = Web3.to_checksum_address(caller_address)

            data = self.contract.functions.getPrescription(
                prescription_id
            ).call({'from': call_from})

            return {
                'success': True,
                'prescription': {
                    'id':          data[0],
                    'patient':     data[1],
                    'doctor':      data[2],
                    'data_hash':   data[3].hex(),
                    'ipfs_hash':   data[4],
                    'timestamp':   data[5],
                    'expiry_date': data[6],
                    'is_active':   data[7],
                    'is_filled':   data[8],
                    'status':      data[9]
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def fill_prescription(self, prescription_id: str) -> dict:
        try:
            existing = self.contract.functions.prescriptions(
                prescription_id
            ).call()
            if existing[5] == 0:
                return {'success': False, 'error': 'Not found'}
            if existing[8]:
                return {'success': False, 'error': 'Already filled'}
            if not existing[7]:
                return {'success': False, 'error': 'Not active'}

            fn = self.contract.functions.fillPrescription(
                prescription_id
            )
            tx = fn.build_transaction({
                'from':     self.account.address,
                'nonce':    self._get_next_nonce(),
                'gas':      self._estimate_gas(fn),
                'gasPrice': self.w3.eth.gas_price,
                'chainId':  settings.BLOCKCHAIN_CONFIG['CHAIN_ID']
            })
            signed  = self.w3.eth.account.sign_transaction(
                tx, self.account.key
            )
            tx_hash = self.w3.eth.send_raw_transaction(
                signed.raw_transaction
            )
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120
            )
            return {
                'success':          receipt['status'] == 1,
                'transaction_hash': tx_hash.hex(),
                'block_number':     receipt['blockNumber'],
                'gas_used':         receipt['gasUsed']
            }
        except Exception as e:
            self._reset_nonce()
            return {'success': False, 'error': str(e)}

    def cancel_prescription(self, prescription_id: str) -> dict:
        try:
            fn = self.contract.functions.cancelPrescription(
                prescription_id
            )
            tx = fn.build_transaction({
                'from':     self.account.address,
                'nonce':    self._get_next_nonce(),
                'gas':      self._estimate_gas(fn),
                'gasPrice': self.w3.eth.gas_price,
                'chainId':  settings.BLOCKCHAIN_CONFIG['CHAIN_ID']
            })
            signed  = self.w3.eth.account.sign_transaction(
                tx, self.account.key
            )
            tx_hash = self.w3.eth.send_raw_transaction(
                signed.raw_transaction
            )
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120
            )
            return {
                'success':          receipt['status'] == 1,
                'transaction_hash': tx_hash.hex()
            }
        except Exception as e:
            self._reset_nonce()
            return {'success': False, 'error': str(e)}

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def get_network_info(self) -> dict:
        return {
            'connected':    self.w3.is_connected(),
            'chain_id':     self.w3.eth.chain_id,
            'block_number': self.w3.eth.block_number,
            'account':      self.account.address,
            'balance':      self.w3.eth.get_balance(
                self.account.address
            )
        }


# ==================== SINGLETON ====================

_manager      = None
_manager_lock = threading.Lock()


def get_blockchain_manager() -> BlockchainManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                try:
                    _manager = BlockchainManager()
                except Exception as e:
                    raise RuntimeError(
                        f"Blockchain init failed: {e}\n"
                        f"Check Ganache is running and .env is correct."
                    )
    return _manager


def reset_blockchain_manager():
    global _manager
    with _manager_lock:
        _manager = None