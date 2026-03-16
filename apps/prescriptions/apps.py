# apps/prescriptions/apps.py

from django.apps import AppConfig


class PrescriptionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'apps.prescriptions'

    def ready(self):
        """
        Called on every server start.
        1. Registers all approved doctors on blockchain
        2. Registers all approved pharmacies on blockchain
        3. Assigns wallets to any patient/walk-in without one
        """
        # Import signals to activate them
        import apps.prescriptions.models  # noqa: F401

        try:
            self._auto_setup()
        except Exception as e:
            # Never crash server startup
            print(f'[apps.py] Auto-setup skipped: {e}')

    def _auto_setup(self):
        print('\n' + '='*50)
        print('[MedChain] 🚀 Server startup — auto-registering blockchain...')
        print('='*50)

        try:
            from apps.blockchain.web3_manager import get_blockchain_manager
            manager = get_blockchain_manager()
            print(f'[MedChain] ✅ Blockchain connected: {manager.account.address}')
        except Exception as e:
            print(f'[MedChain] ⚠️  Blockchain offline: {e}')
            print('[MedChain] ℹ️  Start Ganache and redeploy to enable blockchain features.')
            return

        try:
            from apps.prescriptions.models import (
                Doctor, Pharmacy, Patient, WalkInPatient, UserProfile,
                assign_next_ganache_wallet,
                _register_doctor_on_chain,
                _register_pharmacy_on_chain,
            )

            # ── Doctors ──────────────────────────────────────────
            approved_doctors = Doctor.objects.filter(
                verification_status='approved'
            ).select_related('user', 'user__profile')

            print(f'\n[MedChain] Found {approved_doctors.count()} approved doctors')

            for doctor in approved_doctors:
                try:
                    profile = doctor.user.profile
                    # Auto-assign wallet if missing
                    if not profile.ethereum_address:
                        wallet = assign_next_ganache_wallet()
                        if wallet:
                            profile.ethereum_address = wallet
                            profile.save(update_fields=['ethereum_address'])
                            print(f'   💼 Wallet assigned to Dr. {doctor.user.username}: {wallet}')
                    if profile.ethereum_address:
                        _register_doctor_on_chain(
                            profile.ethereum_address,
                            doctor.user.username
                        )
                except Exception as e:
                    print(f'   ❌ Doctor {doctor.user.username}: {e}')

            # ── Pharmacies ────────────────────────────────────────
            approved_pharmacies = Pharmacy.objects.filter(
                verification_status='approved'
            ).select_related('user', 'user__profile')

            print(f'\n[MedChain] Found {approved_pharmacies.count()} approved pharmacies')

            for pharmacy in approved_pharmacies:
                try:
                    profile = pharmacy.user.profile
                    if not profile.ethereum_address:
                        wallet = assign_next_ganache_wallet()
                        if wallet:
                            profile.ethereum_address = wallet
                            profile.save(update_fields=['ethereum_address'])
                            print(f'   💼 Wallet assigned to {pharmacy.pharmacy_name}: {wallet}')
                    if profile.ethereum_address:
                        _register_pharmacy_on_chain(
                            profile.ethereum_address,
                            pharmacy.pharmacy_name or pharmacy.user.username
                        )
                except Exception as e:
                    print(f'   ❌ Pharmacy {pharmacy.user.username}: {e}')

            # ── Patients without wallet ──────────────────────────
            unassigned_patients = Patient.objects.select_related(
                'user__profile'
            ).filter(
                user__profile__ethereum_address__isnull=True
            ) | Patient.objects.select_related('user__profile').filter(
                user__profile__ethereum_address=''
            )

            if unassigned_patients.exists():
                print(f'\n[MedChain] Assigning wallets to {unassigned_patients.count()} patients...')
                for patient in unassigned_patients:
                    try:
                        wallet = assign_next_ganache_wallet()
                        if wallet:
                            patient.user.profile.ethereum_address = wallet
                            patient.user.profile.save(update_fields=['ethereum_address'])
                            print(f'   💼 Wallet assigned to patient {patient.user.username}: {wallet}')
                    except Exception as e:
                        print(f'   ❌ Patient {patient.user.username}: {e}')

            # ── Walk-in patients without wallet ──────────────────
            unassigned_walkins = WalkInPatient.objects.filter(
                ethereum_address__isnull=True
            ) | WalkInPatient.objects.filter(ethereum_address='')

            if unassigned_walkins.exists():
                print(f'\n[MedChain] Assigning wallets to {unassigned_walkins.count()} walk-in patients...')
                for walkin in unassigned_walkins:
                    try:
                        wallet = assign_next_ganache_wallet()
                        if wallet:
                            WalkInPatient.objects.filter(pk=walkin.pk).update(
                                ethereum_address=wallet
                            )
                            print(f'   💼 Wallet assigned to walk-in {walkin.full_name}: {wallet}')
                    except Exception as e:
                        print(f'   ❌ Walk-in {walkin.full_name}: {e}')

            print('\n[MedChain] ✅ Auto-setup complete!')
            print('='*50 + '\n')

        except Exception as e:
            print(f'[MedChain] ❌ Auto-setup error: {e}')
            import traceback
            traceback.print_exc()