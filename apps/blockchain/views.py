# apps/blockchain/views.py

import json
import re
import functools
import traceback
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required


# ==================== ROLE DECORATOR ====================

def require_role(role):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse(
                    {'success': False, 'error': 'Login required'},
                    status=401
                )
            try:
                if request.user.profile.user_type != role:
                    return JsonResponse(
                        {'success': False,
                         'error': f'Only {role}s allowed'},
                        status=403
                    )
            except Exception:
                return JsonResponse(
                    {'success': False, 'error': 'Profile not found'},
                    status=403
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ==================== HASH HELPER ====================
# SINGLE definition of what fields go into the hash.
# Used by store, verify AND fill — must ALWAYS be identical.

def _build_hash_data(prescription_id, disease, drug,
                     dosage, frequency, duration,
                     instructions, adverse_effects):
    """
    Returns the dict that gets hashed.
    ⚠️  DO NOT add created_at or any timestamp here —
        timestamps differ between creation and verification.
    """
    return {
        'prescription_id': str(prescription_id).strip(),
        'disease':         str(disease).strip(),
        'drug':            str(drug).strip(),
        'dosage':          str(dosage or '').strip(),
        'frequency':       str(frequency or '').strip(),
        'duration':        str(duration or '').strip(),
        'instructions':    str(instructions or '').strip(),
        'adverse_effects': str(adverse_effects or '').strip(),
    }


# ==================== PATIENT RESOLVER ====================

def _resolve_patient_and_walkin(patient_address, walkin_patient_id=None):
    """
    Returns (patient_obj, walkin_obj).
    Exactly one will be non-None when a match is found.

    Resolution order:
      1. Explicit walkin_patient_id from the form  ← highest priority
      2. Wallet address matches a registered Patient
      3. Wallet address matches a WalkInPatient
    """
    from apps.prescriptions.models import UserProfile, WalkInPatient

    patient = None
    walkin  = None

    # 1. Explicit walk-in ID supplied by the doctor dashboard form
    if walkin_patient_id:
        try:
            walkin = WalkInPatient.objects.get(patient_id=walkin_patient_id)
            return patient, walkin
        except WalkInPatient.DoesNotExist:
            pass

    # 2. Try to match wallet address → registered Patient
    try:
        profile = UserProfile.objects.get(ethereum_address=patient_address)
        patient = profile.user.patient
        return patient, walkin
    except Exception:
        pass

    # 3. Try to match wallet address → WalkInPatient
    try:
        walkin = WalkInPatient.objects.get(ethereum_address=patient_address)
    except WalkInPatient.DoesNotExist:
        pass

    return patient, walkin


# ==================== STORE PRESCRIPTION ====================

@login_required
@require_role('doctor')
@require_http_methods(["POST"])
def store_prescription_blockchain(request):
    try:
        data             = json.loads(request.body)
        prescription_id  = data.get('prescription_id', '').strip()
        patient_address  = data.get('patient_address', '').strip()
        disease          = data.get('disease', '').strip()
        drug             = data.get('drug', '').strip()
        dosage           = data.get('dosage', '').strip()
        frequency        = data.get('frequency', '').strip()
        duration         = data.get('duration', '').strip()
        instructions     = data.get('instructions', '').strip()
        adverse_effects  = data.get('adverse_effects', 'None noted').strip()
        # ✅ Walk-in patient ID — passed by doctor dashboard when patient
        #    was looked up by P-XXXXX and type == 'walkin'
        walkin_patient_id = data.get('walkin_patient_id', None)

        # ── Validate required fields ──────────────────────────
        if not all([prescription_id, patient_address, disease, drug]):
            return JsonResponse({
                'success': False,
                'error':   'prescription_id, patient_address, '
                           'disease and drug are required'
            }, status=400)

        if not re.match(r'^0x[a-fA-F0-9]{40}$', patient_address):
            return JsonResponse({
                'success': False,
                'error':   'Invalid patient Ethereum address'
            }, status=400)

        from apps.prescriptions.models import PrescriptionRecord
        from django.utils import timezone
        from datetime import timedelta

        # ── Check doctor ──────────────────────────────────────
        try:
            doctor = request.user.doctor
        except Exception:
            return JsonResponse({
                'success': False,
                'error':   'Doctor profile not found'
            }, status=400)

        if doctor.verification_status == 'pending':
            return JsonResponse({
                'success': False,
                'error':   'Your account is pending admin verification.'
            }, status=403)

        if doctor.verification_status == 'rejected':
            return JsonResponse({
                'success': False,
                'error':   'Your account has been rejected by admin.'
            }, status=403)

        # ── Check wallet ──────────────────────────────────────
        doctor_wallet = getattr(
            request.user.profile, 'ethereum_address', ''
        ) or ''
        if not doctor_wallet:
            return JsonResponse({
                'success': False,
                'error':   'Doctor has no wallet address. '
                           'Contact admin to assign one.'
            }, status=400)

        # ── Blockchain manager ────────────────────────────────
        try:
            from apps.blockchain.web3_manager import get_blockchain_manager
            manager = get_blockchain_manager()
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error':   'Blockchain unavailable. '
                           'Please start Ganache and try again.'
            }, status=503)

        # ── Build hash — NO created_at ────────────────────────
        hash_data = _build_hash_data(
            prescription_id, disease, drug,
            dosage, frequency, duration,
            instructions, adverse_effects
        )
        data_hash = manager.make_data_hash(hash_data)

        print(f'[STORE] hash_data : {hash_data}')
        print(f'[STORE] data_hash : {data_hash.hex()}')

        # ── Blockchain FIRST ──────────────────────────────────
        bc_result = manager.create_prescription(
            prescription_id=prescription_id,
            patient_address=patient_address,
            data_hash=data_hash,
            ipfs_hash=''
        )

        if not bc_result['success']:
            return JsonResponse({
                'success': False,
                'error':   f'Blockchain error: {bc_result["error"]}'
            }, status=400)

        # ── Resolve patient / walk-in ─────────────────────────
        # Works for both registered patients and walk-in patients.
        # walkin_patient_id is the P-XXXXX passed by the new dashboard.
        patient, walkin = _resolve_patient_and_walkin(
            patient_address, walkin_patient_id
        )

        # ── DB save after blockchain confirms ─────────────────
        PrescriptionRecord.objects.create(
            prescription_id     = prescription_id,
            doctor              = doctor,
            patient             = patient,       # registered Patient or None
            walkin_patient      = walkin,        # WalkInPatient or None
            disease             = disease,
            drug                = drug,
            dosage              = dosage,
            frequency           = frequency,
            duration            = duration,
            instructions        = instructions,
            adverse_effects     = adverse_effects,
            doctor_wallet       = doctor_wallet,
            patient_wallet      = patient_address,
            transaction_hash    = bc_result['transaction_hash'],
            block_number        = bc_result['block_number'],
            data_hash           = data_hash.hex(),
            blockchain_verified = True,
            expiry_date         = timezone.now() + timedelta(days=30)
        )

        return JsonResponse({
            'success':          True,
            'prescription_id':  prescription_id,
            'transaction_hash': bc_result['transaction_hash'],
            'block_number':     bc_result['block_number'],
            'data_hash':        data_hash.hex(),
            'message':          'Prescription stored on blockchain ✅'
        })

    except Exception as e:
        print('STORE ERROR:', traceback.format_exc())
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=500
        )


# ==================== GET + VERIFY PRESCRIPTION ====================

@login_required
@require_http_methods(["GET"])
def get_prescription_blockchain(request, prescription_id):
    try:
        from apps.prescriptions.models import PrescriptionRecord

        # ── Get DB record ─────────────────────────────────────
        try:
            rx = PrescriptionRecord.objects.get(
                prescription_id=prescription_id
            )
        except PrescriptionRecord.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': 'Prescription not found'},
                status=404
            )

        if not rx.blockchain_verified or not rx.data_hash:
            return JsonResponse({
                'success': False,
                'error':   'Prescription has no blockchain record.',
                'source':  'unverified'
            }, status=400)

        # ✅ patient_name works for both registered and walk-in patients
        #    via the property defined in models.py
        db_data = {
            'prescription_id':  rx.prescription_id,
            'disease':          rx.disease,
            'drug':             rx.drug,
            'dosage':           rx.dosage or '',
            'frequency':        rx.frequency or '',
            'duration':         rx.duration or '',
            'instructions':     rx.instructions or '',
            'adverse_effects':  rx.adverse_effects or '',
            'is_filled':        rx.is_filled,
            'is_cancelled':     rx.is_cancelled,
            'created_at':       rx.created_at.isoformat(),
            'filled_at':        rx.filled_at.isoformat()
                                if rx.filled_at else None,
            'doctor':           rx.doctor.user.get_full_name()
                                if rx.doctor else '',
            # ✅ Uses patient_name property — works for both types
            'patient':          rx.patient_name,
            'patient_id':       rx.patient_id_str,
            'data_hash':        rx.data_hash or '',
            'transaction_hash': rx.transaction_hash or '',
            'block_number':     rx.block_number or 0,
        }

        # ── Blockchain manager ────────────────────────────────
        try:
            from apps.blockchain.web3_manager import get_blockchain_manager
            manager = get_blockchain_manager()
        except Exception:
            return JsonResponse({
                'success':              True,
                'db_data':              db_data,
                'blockchain_available': False,
                'tampered':             False,
                'source':               'db_only',
                'warning':              'Blockchain offline — '
                                        'hash verification skipped'
            })

        # ── Get blockchain hash ───────────────────────────────
        caller_address = getattr(
            request.user.profile, 'ethereum_address', None
        )
        bc_result = manager.get_prescription(
            prescription_id,
            caller_address=caller_address
        )

        if not bc_result['success']:
            return JsonResponse({
                'success':              True,
                'db_data':              db_data,
                'blockchain_available': False,
                'tampered':             False,
                'source':               'db_only',
                'warning':              'Could not read from blockchain'
            })

        # ── TAMPER DETECTION ──────────────────────────────────
        # Compare DB stored hash vs blockchain hash DIRECTLY.
        # No rehashing needed — both were set at creation time.
        blockchain_hash = bc_result['prescription']['data_hash']
        db_stored_hash  = rx.data_hash

        print(f'[VERIFY] db_hash : {db_stored_hash}')
        print(f'[VERIFY] bc_hash : {blockchain_hash}')

        hashes_match = (db_stored_hash == blockchain_hash)

        return JsonResponse({
            'success':              True,
            'prescription':         bc_result['prescription'],
            'db_data':              db_data,
            'blockchain_available': True,
            'tampered':             not hashes_match,
            'source':               'blockchain+db',
            'verification': {
                'blockchain_hash': blockchain_hash,
                'stored_hash':     db_stored_hash,
                'match':           hashes_match,
            }
        })

    except Exception as e:
        print('VERIFY ERROR:', traceback.format_exc())
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=500
        )


# ==================== FILL PRESCRIPTION ====================

@login_required
@require_role('pharmacy')
@require_http_methods(["POST"])
def fill_prescription_blockchain(request):
    try:
        data            = json.loads(request.body)
        prescription_id = data.get('prescription_id')

        if not prescription_id:
            return JsonResponse(
                {'success': False, 'error': 'prescription_id required'},
                status=400
            )

        from apps.prescriptions.models import PrescriptionRecord
        from django.utils import timezone

        # ── Check pharmacy approved ───────────────────────────
        try:
            pharmacy = request.user.pharmacy
        except Exception:
            return JsonResponse(
                {'success': False, 'error': 'Pharmacy profile not found'},
                status=400
            )

        if pharmacy.verification_status == 'pending':
            return JsonResponse({
                'success': False,
                'error':   'Your pharmacy is pending admin verification.'
            }, status=403)

        if pharmacy.verification_status == 'rejected':
            return JsonResponse({
                'success': False,
                'error':   'Your pharmacy registration was rejected.'
            }, status=403)

        # ── Get DB record ─────────────────────────────────────
        try:
            rx = PrescriptionRecord.objects.get(
                prescription_id=prescription_id
            )
        except PrescriptionRecord.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': 'Prescription not found'},
                status=404
            )

        # ── Validate status ───────────────────────────────────
        if rx.is_filled:
            return JsonResponse(
                {'success': False, 'error': 'Already dispensed'},
                status=400
            )
        if rx.is_cancelled:
            return JsonResponse(
                {'success': False, 'error': 'Prescription is cancelled'},
                status=400
            )
        if rx.expiry_date and timezone.now() > rx.expiry_date:
            return JsonResponse(
                {'success': False, 'error': 'Prescription has expired'},
                status=400
            )
        if not rx.blockchain_verified:
            return JsonResponse({
                'success': False,
                'error':   'Prescription has no blockchain record. '
                           'Cannot dispense.'
            }, status=400)

        # ── Blockchain manager ────────────────────────────────
        try:
            from apps.blockchain.web3_manager import get_blockchain_manager
            manager = get_blockchain_manager()
        except Exception:
            return JsonResponse({
                'success': False,
                'error':   'Blockchain unavailable. '
                           'Start Ganache and try again.'
            }, status=503)

        # ── TAMPER DETECTION ──────────────────────────────────
        # Compare DB stored hash vs blockchain hash DIRECTLY.
        # This is the ONLY correct way — no rehashing.
        bc_get = manager.get_prescription(
            prescription_id,
            caller_address=manager.account.address
        )

        if not bc_get['success']:
            return JsonResponse({
                'success': False,
                'error':   'Could not read prescription from blockchain.'
            }, status=400)

        blockchain_hash = bc_get['prescription']['data_hash']
        db_stored_hash  = rx.data_hash

        print(f'[FILL] db_hash : {db_stored_hash}')
        print(f'[FILL] bc_hash : {blockchain_hash}')
        print(f'[FILL] match   : {db_stored_hash == blockchain_hash}')

        if db_stored_hash != blockchain_hash:
            return JsonResponse({
                'success': False,
                'error':   '⚠️ TAMPER DETECTED: Prescription data '
                           'has been modified. Cannot dispense.'
            }, status=400)

        # ── Fill on blockchain ────────────────────────────────
        bc_result = manager.fill_prescription(prescription_id)

        if not bc_result['success']:
            return JsonResponse({
                'success': False,
                'error':   f'Blockchain rejected: {bc_result["error"]}'
            }, status=400)

        # ── Update DB after blockchain confirms ───────────────
        rx.is_filled        = True
        rx.filled_at        = timezone.now()
        rx.filled_by        = pharmacy
        rx.transaction_hash = bc_result['transaction_hash']
        rx.block_number     = bc_result['block_number']
        rx.save()

        return JsonResponse({
            'success':              True,
            'transaction_hash':     bc_result['transaction_hash'],
            'block_number':         bc_result['block_number'],
            'blockchain_confirmed': True,
            'message':              'Prescription dispensed ✅'
        })

    except Exception as e:
        print('FILL ERROR:', traceback.format_exc())
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=500
        )


# ==================== CANCEL PRESCRIPTION ====================

@login_required
@require_role('doctor')
@require_http_methods(["POST"])
def cancel_prescription_blockchain(request):
    try:
        data            = json.loads(request.body)
        prescription_id = data.get('prescription_id')

        if not prescription_id:
            return JsonResponse(
                {'success': False, 'error': 'prescription_id required'},
                status=400
            )

        try:
            from apps.blockchain.web3_manager import get_blockchain_manager
            manager = get_blockchain_manager()
        except Exception:
            return JsonResponse({
                'success': False,
                'error':   'Blockchain unavailable. Start Ganache.'
            }, status=503)

        bc_result = manager.cancel_prescription(prescription_id)

        if not bc_result['success']:
            return JsonResponse({
                'success': False,
                'error':   f'Blockchain error: {bc_result["error"]}'
            }, status=400)

        from apps.prescriptions.models import PrescriptionRecord
        from django.utils import timezone
        try:
            rx              = PrescriptionRecord.objects.get(
                prescription_id=prescription_id,
                doctor__user=request.user
            )
            rx.is_cancelled = True
            rx.cancelled_at = timezone.now()
            rx.save()
        except PrescriptionRecord.DoesNotExist:
            pass

        return JsonResponse({
            'success':          True,
            'transaction_hash': bc_result['transaction_hash'],
            'message':          'Prescription cancelled ✅'
        })

    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=500
        )


# ==================== BLOCKCHAIN STATUS ====================

@login_required
@require_http_methods(["GET"])
def blockchain_status(request):
    try:
        from apps.blockchain.web3_manager import get_blockchain_manager
        manager = get_blockchain_manager()
        info    = manager.get_network_info()
        return JsonResponse({
            'success':      True,
            'connected':    info['connected'],
            'chain_id':     info['chain_id'],
            'block_number': info['block_number'],
            'account':      info['account'],
            'contract':     manager.contract.address
        })
    except Exception as e:
        return JsonResponse({
            'success':   False,
            'connected': False,
            'error':     str(e)
        })