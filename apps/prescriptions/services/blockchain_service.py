# apps/prescriptions/services/blockchain_service.py
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BlockchainService:
    """
    Thin wrapper over web3_manager.
    Handles hash generation and delegates to manager.
    """

    def __init__(self):
        from apps.blockchain.web3_manager import (
            get_blockchain_manager, BlockchainManager
        )
        try:
            self.manager = get_blockchain_manager()
        except Exception as e:
            logger.error(f"BlockchainService init failed: {e}")
            self.manager = None

    def _make_hash(self, data: dict) -> bytes:
        from apps.blockchain.web3_manager import BlockchainManager
        return BlockchainManager.make_data_hash(data)

    def store_prescription(
        self,
        prescription_id: str,
        prescription_data: dict,
        patient_address: str,
        ipfs_hash: str = ""
    ) -> dict:
        """
        Hash the prescription data, then store hash on blockchain.
        Full medical data stays in Django DB only.
        """
        if not self.manager:
            return {'success': False, 'error': 'Blockchain not connected'}

        try:
            # Generate hash from full medical data
            data_hash = self._make_hash(prescription_data)

            result = self.manager.create_prescription(
                prescription_id=prescription_id,
                patient_address=patient_address,
                data_hash=data_hash,
                ipfs_hash=ipfs_hash
            )

            if result['success']:
                result['data_hash'] = data_hash.hex()

            return result

        except Exception as e:
            logger.error(f"store_prescription error: {e}")
            return {'success': False, 'error': str(e)}

    def verify_prescription(
        self,
        prescription_id: str,
        prescription_data: dict
    ) -> dict:
        """
        Verify data integrity — rehash DB data and compare with chain.
        If tampered=True, someone modified the DB record.
        """
        if not self.manager:
            return {'success': False, 'error': 'Blockchain not connected'}

        return self.manager.verify_prescription(
            prescription_id, prescription_data
        )

    def get_prescription_details(self, prescription_id: str) -> dict:
        if not self.manager:
            return {'success': False, 'error': 'Blockchain not connected'}
        return self.manager.get_prescription(prescription_id)

    def dispense_prescription(self, prescription_id: str) -> dict:
        if not self.manager:
            return {'success': False, 'error': 'Blockchain not connected'}
        return self.manager.fill_prescription(prescription_id)

    def cancel_prescription(self, prescription_id: str) -> dict:
        if not self.manager:
            return {'success': False, 'error': 'Blockchain not connected'}
        return self.manager.cancel_prescription(prescription_id)

    def is_connected(self) -> bool:
        return self.manager.is_connected() if self.manager else False