# apps/blockchain/views.py

import json
import hashlib
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(["POST"])
def store_prescription_blockchain(request):
    """Store prescription on blockchain"""
    try:
        data = json.loads(request.body)
        
        patient = data.get('patient_address')
        disease = data.get('disease')
        drug = data.get('drug')
        adverse_effects = data.get('adverse_effects', '')
        
        # Validate
        if not all([patient, disease, drug]):
            return JsonResponse({
                'success': False,
                'error': 'patient_address, disease and drug are required'
            }, status=400)
        
        # Generate unique prescription ID
        timestamp = int(datetime.now().timestamp())
        prescription_id = hashlib.sha256(
            f"{patient}{timestamp}".encode()
        ).hexdigest()[:16]
        
        ipfs_hash = f"QmMedChain{prescription_id[:8]}"
        
        # Get manager lazily (only when needed!)
        from apps.blockchain.web3_manager import get_blockchain_manager
        manager = get_blockchain_manager()
        
        # Store on blockchain
        result = manager.create_prescription(
            prescription_id=prescription_id,
            patient_address=patient,
            disease=disease,
            drug=drug,
            adverse_effects=adverse_effects,
            ipfs_hash=ipfs_hash
        )
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'prescription_id': prescription_id,
                'transaction_hash': result['transaction_hash'],
                'block_number': result['block_number'],
                'gas_used': result['gas_used'],
                'ipfs_hash': ipfs_hash
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result['error']
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_prescription_blockchain(request, prescription_id):
    """Get prescription from blockchain"""
    try:
        from apps.blockchain.web3_manager import get_blockchain_manager
        manager = get_blockchain_manager()
        
        result = manager.get_prescription(prescription_id)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'prescription': result['prescription']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result['error']
            }, status=404)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def fill_prescription_blockchain(request):
    """Mark prescription as filled - called from Pharmacy"""
    try:
        data = json.loads(request.body)
        prescription_id = data.get('prescription_id')
        
        if not prescription_id:
            return JsonResponse({
                'success': False,
                'error': 'prescription_id is required'
            }, status=400)
        
        from apps.blockchain.web3_manager import get_blockchain_manager
        manager = get_blockchain_manager()
        
        result = manager.fill_prescription(prescription_id)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'transaction_hash': result['transaction_hash'],
                'block_number': result['block_number'],
                'message': 'Prescription marked as filled!'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result['error']
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def blockchain_status(request):
    """Check blockchain connection"""
    try:
        from apps.blockchain.web3_manager import get_blockchain_manager
        manager = get_blockchain_manager()
        
        return JsonResponse({
            'success': True,
            'connected': manager.w3.is_connected(),
            'account': manager.account.address,
            'contract': manager.contract.address
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'connected': False,
            'error': str(e)
        })