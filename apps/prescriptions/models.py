# apps/prescriptions/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
import re
import random
import string


# ==================== VALIDATORS ====================

phone_validator = RegexValidator(
    regex=r'^[1-9][0-9]{9}$',
    message='Phone must be 10 digits, cannot start with 0'
)

ethereum_validator = RegexValidator(
    regex=r'^0x[a-fA-F0-9]{40}$',
    message='Invalid Ethereum address. Must be 0x + 40 hex chars'
)


def validate_username(value):
    if not re.match(r'^[a-zA-Z0-9_]+$', value):
        raise ValidationError(
            'Username can only contain letters, numbers, underscores'
        )
    if len(value) < 3:
        raise ValidationError('Username must be at least 3 characters')


# ==================== AUTO WALLET HELPER ====================

def assign_next_ganache_wallet():
    """
    Automatically assigns the next free Ganache wallet account
    to a newly approved user.
    Admin never needs to manually set wallet addresses.
    """
    try:
        from apps.blockchain.web3_manager import get_blockchain_manager
        m = get_blockchain_manager()

        # Get all 10 Ganache accounts
        accounts = m.w3.eth.accounts

        # Get already-assigned wallets from DB
        assigned = set(
            UserProfile.objects.filter(
                ethereum_address__isnull=False
            ).exclude(
                ethereum_address=''
            ).values_list('ethereum_address', flat=True)
        )

        # Account 0 is always the backend/admin wallet — skip it
        backend = m.account.address.lower()

        for acc in accounts:
            if acc.lower() == backend:
                continue
            if acc not in assigned and acc.lower() not in assigned:
                print(f'   🔑 Auto-assigned wallet: {acc}')
                return acc

        print('   ⚠️  No free Ganache accounts available!')
        return None

    except Exception as e:
        print(f'   ⚠️  Auto wallet assignment failed: {e}')
        return None


# ==================== PATIENT ID GENERATOR ====================

def generate_patient_id():
    """Generate unique P-XXXXX patient ID"""
    while True:
        chars = string.ascii_uppercase + string.digits
        suffix = ''.join(random.choices(chars, k=5))
        pid = f'P-{suffix}'
        # Check uniqueness across both Patient and WalkInPatient
        if not Patient.objects.filter(patient_id=pid).exists() and \
           not WalkInPatient.objects.filter(patient_id=pid).exists():
            return pid


# ==================== MODELS ====================

class UserProfile(models.Model):
    USER_TYPE_CHOICES = [
        ('doctor',   'Doctor'),
        ('patient',  'Patient'),
        ('pharmacy', 'Pharmacy'),
    ]
    user             = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile'
    )
    user_type        = models.CharField(
        max_length=20, choices=USER_TYPE_CHOICES
    )
    phone            = models.CharField(
        max_length=15, validators=[phone_validator]
    )
    ethereum_address = models.CharField(
        max_length=42, blank=True, null=True,
        validators=[ethereum_validator]
    )
    is_verified      = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_user_type_display()}"

    class Meta:
        verbose_name = 'User Profile'
        indexes = [
            models.Index(fields=['user_type']),
            models.Index(fields=['ethereum_address']),
        ]


class Doctor(models.Model):
    VERIFICATION_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user                = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='doctor'
    )
    # ✅ LICENSE REQUIRED
    license_number      = models.CharField(
        max_length=50,
        help_text='Medical Council License Number (required)'
    )
    specialization      = models.CharField(
        max_length=100, blank=True, default='General Physician'
    )
    hospital            = models.CharField(
        max_length=200, blank=True, default=''
    )
    license_document    = models.FileField(
        upload_to='doctor_licenses/',
        null=True, blank=True
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_CHOICES,
        default='pending'
    )
    rejection_reason    = models.CharField(
        max_length=255, blank=True, default=''
    )
    created_at          = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name()} [{self.license_number}]"

    class Meta:
        verbose_name = 'Doctor'


class Patient(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('Unknown', 'Unknown'),
    ]
    user          = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='patient'
    )
    # ✅ Unique Patient ID for self-registered patients
    patient_id    = models.CharField(
        max_length=20, unique=True, blank=True,
        help_text='System-generated Patient ID (P-XXXXX)'
    )
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group   = models.CharField(
        max_length=10, blank=True, choices=BLOOD_GROUP_CHOICES,
        default='Unknown'
    )
    gender        = models.CharField(
        max_length=10, blank=True, default='',
        choices=[('Male','Male'),('Female','Female'),('Other','Other')]
    )
    allergies     = models.TextField(blank=True)
    address       = models.TextField(blank=True, default='')
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Patient: {self.user.get_full_name()} [{self.patient_id}]"

    def save(self, *args, **kwargs):
        if not self.patient_id:
            self.patient_id = generate_patient_id()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def phone(self):
        try:
            return self.user.profile.phone
        except Exception:
            return ''

    @property
    def age(self):
        if self.date_of_birth:
            from django.utils import timezone
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) <
                (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    @property
    def wallet(self):
        try:
            return self.user.profile.ethereum_address
        except Exception:
            return None


class WalkInPatient(models.Model):
    """
    Patients registered directly by a doctor (walk-in patients).
    No Django User account needed.
    Doctor registers them on-the-spot.
    """
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('Unknown', 'Unknown'),
    ]
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    # ✅ Unique Patient ID
    patient_id      = models.CharField(
        max_length=20, unique=True,
        help_text='Auto-generated P-XXXXX ID'
    )
    full_name       = models.CharField(max_length=200)
    date_of_birth   = models.DateField(null=True, blank=True)
    gender          = models.CharField(
        max_length=10, choices=GENDER_CHOICES, default='Male'
    )
    phone           = models.CharField(
        max_length=15, validators=[phone_validator]
    )
    blood_group     = models.CharField(
        max_length=10, choices=BLOOD_GROUP_CHOICES, default='Unknown'
    )
    address         = models.TextField(blank=True, default='')
    allergies       = models.TextField(blank=True, default='')

    # ✅ Auto-assigned Ethereum wallet
    ethereum_address = models.CharField(
        max_length=42, blank=True, null=True
    )

    # Doctor who registered this patient
    registered_by   = models.ForeignKey(
        Doctor, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registered_patients'
    )

    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"WalkIn: {self.full_name} [{self.patient_id}]"

    def save(self, *args, **kwargs):
        if not self.patient_id:
            self.patient_id = generate_patient_id()
        super().save(*args, **kwargs)

    @property
    def age(self):
        if self.date_of_birth:
            from django.utils import timezone
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) <
                (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    class Meta:
        verbose_name = 'Walk-in Patient'
        verbose_name_plural = 'Walk-in Patients'
        ordering = ['-created_at']


class Pharmacy(models.Model):
    VERIFICATION_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user                = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='pharmacy'
    )
    pharmacy_name       = models.CharField(
        max_length=200, blank=True, default=''
    )
    # ✅ LICENSE REQUIRED
    license_number      = models.CharField(
        max_length=50,
        help_text='Drug Authority License Number (required)'
    )
    address             = models.TextField(blank=True, default='')
    license_document    = models.FileField(
        upload_to='pharmacy_licenses/',
        null=True, blank=True
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_CHOICES,
        default='pending'
    )
    rejection_reason    = models.CharField(
        max_length=255, blank=True, default=''
    )
    created_at          = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pharmacy_name or self.user.get_full_name()} [{self.license_number}]"

    class Meta:
        verbose_name_plural = 'Pharmacies'


class PrescriptionRecord(models.Model):
    prescription_id     = models.CharField(
        max_length=64, unique=True
    )
    doctor              = models.ForeignKey(
        Doctor, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='prescriptions'
    )
    # ✅ Either registered patient OR walk-in patient
    patient             = models.ForeignKey(
        Patient, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='prescriptions'
    )
    walkin_patient      = models.ForeignKey(
        WalkInPatient, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='prescriptions'
    )
    filled_by           = models.ForeignKey(
        Pharmacy, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dispensed_prescriptions'
    )
    # Blockchain
    transaction_hash    = models.CharField(
        max_length=66, blank=True, null=True
    )
    block_number        = models.IntegerField(blank=True, null=True)
    data_hash           = models.CharField(
        max_length=64, blank=True, null=True
    )
    blockchain_verified = models.BooleanField(default=False)
    doctor_wallet       = models.CharField(
        max_length=42, blank=True, null=True
    )
    patient_wallet      = models.CharField(
        max_length=42, blank=True, null=True
    )
    # Medical data
    disease             = models.CharField(max_length=200)
    drug                = models.TextField()
    dosage              = models.CharField(
        max_length=200, blank=True, null=True
    )
    frequency           = models.CharField(
        max_length=200, blank=True, null=True
    )
    duration            = models.CharField(
        max_length=100, blank=True, null=True
    )
    instructions        = models.TextField(blank=True, null=True)
    adverse_effects     = models.TextField(blank=True, null=True)
    # Status
    is_filled           = models.BooleanField(default=False)
    is_cancelled        = models.BooleanField(default=False)
    # Timestamps
    created_at          = models.DateTimeField(auto_now_add=True)
    filled_at           = models.DateTimeField(null=True, blank=True)
    cancelled_at        = models.DateTimeField(null=True, blank=True)
    expiry_date         = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Prescription {self.prescription_id}"

    @property
    def patient_name(self):
        """Returns patient name regardless of type"""
        if self.patient:
            return self.patient.user.get_full_name()
        if self.walkin_patient:
            return self.walkin_patient.full_name
        return 'Unknown'

    @property
    def patient_id_str(self):
        """Returns patient ID regardless of type"""
        if self.patient:
            return self.patient.patient_id
        if self.walkin_patient:
            return self.walkin_patient.patient_id
        return 'N/A'

    @property
    def is_expired(self):
        from django.utils import timezone
        if self.expiry_date:
            return timezone.now() > self.expiry_date
        return False

    class Meta:
        ordering        = ['-created_at']
        verbose_name    = 'Prescription Record'
        indexes = [
            models.Index(fields=['prescription_id']),
            models.Index(fields=['is_filled']),
            models.Index(fields=['is_cancelled']),
        ]


# ==================== SIGNALS ====================

@receiver(post_save, sender=Doctor)
def auto_register_doctor_on_approval(sender, instance, **kwargs):
    """
    Admin approves doctor → auto-assign wallet → register on blockchain
    Doctor never touches Ganache manually.
    """
    if instance.verification_status != 'approved':
        return

    try:
        profile = instance.user.profile

        # Auto-assign wallet if not already set
        if not profile.ethereum_address:
            wallet = assign_next_ganache_wallet()
            if wallet:
                profile.ethereum_address = wallet
                profile.save(update_fields=['ethereum_address'])
                print(f'   ✅ Wallet auto-assigned to Dr. {instance.user.username}: {wallet}')
            else:
                print(f'   ⚠️  No wallet available for Dr. {instance.user.username}')
                return

        wallet = profile.ethereum_address
        _register_doctor_on_chain(wallet, instance.user.username)

    except Exception as e:
        print(f'Auto register doctor failed: {e}')


@receiver(post_save, sender=Pharmacy)
def auto_register_pharmacy_on_approval(sender, instance, **kwargs):
    """
    Admin approves pharmacy → auto-assign wallet → register on blockchain
    Pharmacy never touches Ganache manually.
    """
    if instance.verification_status != 'approved':
        return

    try:
        profile = instance.user.profile

        # Auto-assign wallet if not already set
        if not profile.ethereum_address:
            wallet = assign_next_ganache_wallet()
            if wallet:
                profile.ethereum_address = wallet
                profile.save(update_fields=['ethereum_address'])
                print(f'   ✅ Wallet auto-assigned to {instance.pharmacy_name}: {wallet}')
            else:
                print(f'   ⚠️  No wallet available for {instance.pharmacy_name}')
                return

        wallet = profile.ethereum_address
        _register_pharmacy_on_chain(wallet, instance.pharmacy_name)

    except Exception as e:
        print(f'Auto register pharmacy failed: {e}')


@receiver(post_save, sender=Patient)
def auto_assign_patient_wallet(sender, instance, created, **kwargs):
    """
    New patient registered → auto-assign blockchain wallet
    Patient never needs to know about wallets.
    """
    if not created:
        return
    try:
        profile = instance.user.profile
        if not profile.ethereum_address:
            wallet = assign_next_ganache_wallet()
            if wallet:
                profile.ethereum_address = wallet
                profile.save(update_fields=['ethereum_address'])
                print(f'   ✅ Wallet auto-assigned to patient {instance.user.username}: {wallet}')
    except Exception as e:
        print(f'Auto assign patient wallet failed: {e}')


@receiver(post_save, sender=WalkInPatient)
def auto_assign_walkin_wallet(sender, instance, created, **kwargs):
    """
    Doctor registers walk-in patient → auto-assign wallet
    """
    if not created:
        return
    if not instance.ethereum_address:
        try:
            wallet = assign_next_ganache_wallet()
            if wallet:
                WalkInPatient.objects.filter(pk=instance.pk).update(
                    ethereum_address=wallet
                )
                print(f'   ✅ Wallet auto-assigned to walk-in {instance.full_name}: {wallet}')
        except Exception as e:
            print(f'Auto assign walk-in wallet failed: {e}')


# ==================== BLOCKCHAIN HELPERS ====================

def _register_doctor_on_chain(wallet, name):
    try:
        from apps.blockchain.web3_manager import get_blockchain_manager
        m = get_blockchain_manager()
        if not m.contract.functions.isDoctor(wallet).call():
            m.contract.functions.registerDoctor(
                wallet
            ).transact({'from': m.account.address})
            print(f'   ✅ Doctor registered on blockchain: {name}')
        else:
            print(f'   ✓  Doctor already on blockchain: {name}')
    except Exception as e:
        print(f'   ❌ Doctor blockchain registration failed: {name}: {e}')


def _register_pharmacy_on_chain(wallet, name):
    try:
        from apps.blockchain.web3_manager import get_blockchain_manager
        m = get_blockchain_manager()
        if not m.contract.functions.isPharmacy(wallet).call():
            m.contract.functions.registerPharmacy(
                wallet
            ).transact({'from': m.account.address})
            print(f'   ✅ Pharmacy registered on blockchain: {name}')
        else:
            print(f'   ✓  Pharmacy already on blockchain: {name}')
    except Exception as e:
        print(f'   ❌ Pharmacy blockchain registration failed: {name}: {e}')