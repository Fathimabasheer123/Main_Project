# apps/prescriptions/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    UserProfile, Doctor, Patient, Pharmacy,
    WalkInPatient, PrescriptionRecord
)


# ==================== INLINE ====================

class DoctorInline(admin.StackedInline):
    model  = Doctor
    extra  = 0
    fields = ('license_number', 'specialization', 'hospital',
              'verification_status', 'rejection_reason')


class PatientInline(admin.StackedInline):
    model  = Patient
    extra  = 0
    fields = ('patient_id', 'date_of_birth', 'blood_group',
              'gender', 'allergies')
    readonly_fields = ('patient_id',)


class PharmacyInline(admin.StackedInline):
    model  = Pharmacy
    extra  = 0
    fields = ('pharmacy_name', 'license_number', 'address',
              'verification_status', 'rejection_reason')


# ==================== ACTIONS ====================

def approve_and_assign_wallet(modeladmin, request, queryset):
    """
    Admin action: Approve selected doctors/pharmacies.
    Wallet is auto-assigned via the post_save signal in models.py.
    """
    for obj in queryset:
        if obj.verification_status != 'approved':
            obj.verification_status = 'approved'
            obj.save()  # triggers post_save signal → auto wallet + blockchain reg
    modeladmin.message_user(
        request,
        f'✅ {queryset.count()} record(s) approved. Wallets auto-assigned via signals.'
    )

approve_and_assign_wallet.short_description = '✅ Approve & Auto-Assign Wallets'


def reject_selected(modeladmin, request, queryset):
    queryset.update(verification_status='rejected')
    modeladmin.message_user(request, f'❌ {queryset.count()} record(s) rejected.')

reject_selected.short_description = '❌ Reject Selected'


# ==================== USER PROFILE ADMIN ====================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'user_type', 'phone',
                    'wallet_display', 'is_verified', 'created_at']
    list_filter  = ['user_type', 'is_verified']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['created_at', 'updated_at']
    fields = ['user', 'user_type', 'phone', 'ethereum_address',
              'is_verified', 'created_at', 'updated_at']

    def wallet_display(self, obj):
        if obj.ethereum_address:
            addr = obj.ethereum_address
            return format_html(
                '<code style="font-size:11px;color:#0369a1;">{}</code>',
                addr[:10] + '...' + addr[-6:]
            )
        return format_html('<span style="color:#94a3b8;">Not assigned</span>')
    wallet_display.short_description = 'Wallet'


# ==================== DOCTOR ADMIN ====================

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display  = ['doctor_name', 'license_number', 'specialization',
                     'hospital', 'status_badge', 'wallet_badge', 'created_at']
    list_filter   = ['verification_status', 'specialization']
    search_fields = ['user__username', 'user__first_name', 'user__last_name',
                     'license_number']
    actions       = [approve_and_assign_wallet, reject_selected]
    readonly_fields = ['created_at']
    fields = ['user', 'license_number', 'specialization', 'hospital',
              'license_document', 'verification_status', 'rejection_reason',
              'created_at']

    def doctor_name(self, obj):
        return f'Dr. {obj.user.get_full_name()}'
    doctor_name.short_description = 'Doctor'

    def status_badge(self, obj):
        colors = {
            'approved': ('#d1fae5', '#065f46'),
            'pending':  ('#fef3c7', '#92400e'),
            'rejected': ('#fee2e2', '#991b1b'),
        }
        bg, fg = colors.get(obj.verification_status, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:20px;font-size:11px;font-weight:700;">{}</span>',
            bg, fg, obj.get_verification_status_display()
        )
    status_badge.short_description = 'Status'

    def wallet_badge(self, obj):
        try:
            addr = obj.user.profile.ethereum_address
            if addr:
                return format_html(
                    '<code style="font-size:11px;color:#0369a1;">'
                    '{}...{}</code>', addr[:8], addr[-4:]
                )
        except Exception:
            pass
        return format_html('<span style="color:#94a3b8;font-size:11px;">Auto on approval</span>')
    wallet_badge.short_description = 'Wallet'


# ==================== PHARMACY ADMIN ====================

@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display  = ['pharmacy_name', 'license_number',
                     'status_badge', 'wallet_badge', 'created_at']
    list_filter   = ['verification_status']
    search_fields = ['user__username', 'pharmacy_name', 'license_number']
    actions       = [approve_and_assign_wallet, reject_selected]
    readonly_fields = ['created_at']
    fields = ['user', 'pharmacy_name', 'license_number', 'address',
              'license_document', 'verification_status', 'rejection_reason',
              'created_at']

    def status_badge(self, obj):
        colors = {
            'approved': ('#d1fae5', '#065f46'),
            'pending':  ('#fef3c7', '#92400e'),
            'rejected': ('#fee2e2', '#991b1b'),
        }
        bg, fg = colors.get(obj.verification_status, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:20px;font-size:11px;font-weight:700;">{}</span>',
            bg, fg, obj.get_verification_status_display()
        )
    status_badge.short_description = 'Status'

    def wallet_badge(self, obj):
        try:
            addr = obj.user.profile.ethereum_address
            if addr:
                return format_html(
                    '<code style="font-size:11px;color:#f59e0b;">'
                    '{}...{}</code>', addr[:8], addr[-4:]
                )
        except Exception:
            pass
        return format_html('<span style="color:#94a3b8;font-size:11px;">Auto on approval</span>')
    wallet_badge.short_description = 'Wallet'


# ==================== PATIENT ADMIN ====================

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display  = ['patient_name', 'patient_id', 'blood_group',
                     'gender', 'wallet_badge', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name',
                     'patient_id']
    list_filter   = ['blood_group', 'gender']
    readonly_fields = ['patient_id', 'created_at']

    def patient_name(self, obj):
        return obj.user.get_full_name()
    patient_name.short_description = 'Name'

    def wallet_badge(self, obj):
        try:
            addr = obj.user.profile.ethereum_address
            if addr:
                return format_html(
                    '<code style="font-size:11px;color:#10b981;">'
                    '{}...{}</code>', addr[:8], addr[-4:]
                )
        except Exception:
            pass
        return format_html('<span style="color:#94a3b8;font-size:11px;">Auto-assigned</span>')
    wallet_badge.short_description = 'Wallet'


# ==================== WALK-IN PATIENT ADMIN ====================

@admin.register(WalkInPatient)
class WalkInPatientAdmin(admin.ModelAdmin):
    list_display  = ['patient_id', 'full_name', 'phone',
                     'gender', 'blood_group', 'registered_by',
                     'wallet_badge', 'created_at']
    search_fields = ['patient_id', 'full_name', 'phone']
    list_filter   = ['gender', 'blood_group']
    readonly_fields = ['patient_id', 'ethereum_address', 'created_at']
    fields = ['patient_id', 'full_name', 'date_of_birth', 'gender',
              'phone', 'blood_group', 'address', 'allergies',
              'ethereum_address', 'registered_by', 'created_at']

    def wallet_badge(self, obj):
        if obj.ethereum_address:
            addr = obj.ethereum_address
            return format_html(
                '<code style="font-size:11px;color:#10b981;">'
                '{}...{}</code>', addr[:8], addr[-4:]
            )
        return format_html('<span style="color:#94a3b8;font-size:11px;">Not assigned</span>')
    wallet_badge.short_description = 'Wallet'


# ==================== PRESCRIPTION ADMIN ====================

@admin.register(PrescriptionRecord)
class PrescriptionRecordAdmin(admin.ModelAdmin):
    list_display  = ['prescription_id', 'patient_display', 'doctor_name',
                     'disease', 'drug_short', 'status_badge',
                     'blockchain_badge', 'created_at']
    list_filter   = ['is_filled', 'is_cancelled', 'blockchain_verified']
    search_fields = ['prescription_id', 'disease', 'drug',
                     'patient__user__username',
                     'walkin_patient__full_name']
    readonly_fields = ['prescription_id', 'transaction_hash', 'block_number',
                       'data_hash', 'blockchain_verified',
                       'doctor_wallet', 'patient_wallet', 'created_at']

    def patient_display(self, obj):
        if obj.patient:
            return f'{obj.patient.user.get_full_name()} [{obj.patient.patient_id}]'
        if obj.walkin_patient:
            return f'{obj.walkin_patient.full_name} [{obj.walkin_patient.patient_id}] (Walk-in)'
        return 'Unknown'
    patient_display.short_description = 'Patient'

    def doctor_name(self, obj):
        return f'Dr. {obj.doctor.user.get_full_name()}' if obj.doctor else '—'
    doctor_name.short_description = 'Doctor'

    def drug_short(self, obj):
        return obj.drug[:30] + '...' if len(obj.drug) > 30 else obj.drug
    drug_short.short_description = 'Drug'

    def status_badge(self, obj):
        if obj.is_cancelled:
            return format_html(
                '<span style="background:#fee2e2;color:#991b1b;'
                'padding:2px 8px;border-radius:20px;font-size:11px;">Cancelled</span>'
            )
        if obj.is_filled:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;'
                'padding:2px 8px;border-radius:20px;font-size:11px;">✓ Filled</span>'
            )
        if obj.expiry_date and timezone.now() > obj.expiry_date:
            return format_html(
                '<span style="background:#f1f5f9;color:#64748b;'
                'padding:2px 8px;border-radius:20px;font-size:11px;">Expired</span>'
            )
        return format_html(
            '<span style="background:#fef3c7;color:#92400e;'
            'padding:2px 8px;border-radius:20px;font-size:11px;">Pending</span>'
        )
    status_badge.short_description = 'Status'

    def blockchain_badge(self, obj):
        if obj.blockchain_verified:
            return format_html(
                '<span style="background:#dbeafe;color:#1d4ed8;'
                'padding:2px 8px;border-radius:20px;font-size:11px;">⛓️ On-chain</span>'
            )
        return format_html(
            '<span style="background:#f1f5f9;color:#94a3b8;'
            'padding:2px 8px;border-radius:20px;font-size:11px;">DB only</span>'
        )
    blockchain_badge.short_description = 'Blockchain'