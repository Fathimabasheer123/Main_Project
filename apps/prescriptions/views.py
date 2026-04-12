# apps/prescriptions/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import models as db_models
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from datetime import timedelta
from .forms import RegisterForm
from .models import (
    UserProfile, PrescriptionRecord,
    Doctor, Patient, Pharmacy, WalkInPatient,
    Notification
)


# ==================== HELPERS ====================

def check_role(request, role):
    try:
        return request.user.profile.user_type == role
    except Exception:
        return False


# ==================== PUBLIC VIEWS ====================

def index(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('/admin/')
        return redirect('dashboard')
    return render(request, 'home.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user            = form.save(commit=False)
                user.first_name = form.cleaned_data['first_name']
                user.last_name  = form.cleaned_data['last_name']
                user.email      = form.cleaned_data['email']
                user.save()

                user_type = form.cleaned_data['user_type']

                UserProfile.objects.create(
                    user      = user,
                    user_type = user_type,
                    phone     = form.cleaned_data['phone']
                )

                if user_type == 'doctor':
                    license_no = request.POST.get(
                        'license_number', ''
                    ).strip()
                    if not license_no:
                        user.delete()
                        messages.error(
                            request,
                            'Medical License Number is required '
                            'for doctors.'
                        )
                        return render(
                            request, 'auth/register.html',
                            {'form': form}
                        )

                    doctor = Doctor.objects.create(
                        user                = user,
                        license_number      = license_no,
                        specialization      = request.POST.get(
                            'specialization', 'General Physician'
                        ).strip(),
                        hospital            = request.POST.get(
                            'hospital', ''
                        ).strip(),
                        verification_status = 'pending'
                    )
                    if request.FILES.get('license_document'):
                        doctor.license_document = (
                            request.FILES['license_document']
                        )
                        doctor.save()

                    messages.success(
                        request,
                        '✅ Registration submitted! Admin will verify '
                        'your Medical License Number before granting '
                        'access.'
                    )
                    return redirect('login')

                elif user_type == 'pharmacy':
                    license_no = request.POST.get(
                        'drug_license', ''
                    ).strip()
                    if not license_no:
                        user.delete()
                        messages.error(
                            request,
                            'Drug License Number is required '
                            'for pharmacies.'
                        )
                        return render(
                            request, 'auth/register.html',
                            {'form': form}
                        )

                    pharmacy = Pharmacy.objects.create(
                        user                = user,
                        pharmacy_name       = request.POST.get(
                            'pharmacy_name', ''
                        ).strip(),
                        license_number      = license_no,
                        address             = request.POST.get(
                            'address', ''
                        ).strip(),
                        verification_status = 'pending'
                    )
                    if request.FILES.get('license_document'):
                        pharmacy.license_document = (
                            request.FILES['license_document']
                        )
                        pharmacy.save()

                    messages.success(
                        request,
                        '✅ Registration submitted! Admin will verify '
                        'your Pharmacy License Number before granting '
                        'access.'
                    )
                    return redirect('login')

                elif user_type == 'patient':
                    dob          = request.POST.get(
                        'date_of_birth', ''
                    ).strip()
                    blood        = request.POST.get(
                        'blood_group', 'Unknown'
                    ).strip()
                    gender       = request.POST.get('gender', '').strip()
                    walkin_id    = request.POST.get(
                        'walkin_patient_id', ''
                    ).strip().upper()
                    walkin_phone = request.POST.get(
                        'walkin_phone', ''
                    ).strip()

                    patient = Patient.objects.create(
                        user        = user,
                        blood_group = blood or 'Unknown',
                        gender      = gender,
                    )
                    if dob:
                        from datetime import date
                        try:
                            patient.date_of_birth = (
                                date.fromisoformat(dob)
                            )
                            patient.save()
                        except Exception:
                            pass

                    # Claim walk-in record if ID + phone provided
                    if walkin_id and walkin_phone:
                        try:
                            walkin = WalkInPatient.objects.get(
                                patient_id = walkin_id,
                                phone      = walkin_phone
                            )
                            PrescriptionRecord.objects.filter(
                                walkin_patient=walkin
                            ).update(patient=patient)

                            if not patient.blood_group or \
                               patient.blood_group == 'Unknown':
                                patient.blood_group = walkin.blood_group
                            if not patient.allergies:
                                patient.allergies = walkin.allergies
                            patient.save()

                            if walkin.ethereum_address and \
                               not user.profile.ethereum_address:
                                profile = user.profile
                                profile.ethereum_address = (
                                    walkin.ethereum_address
                                )
                                profile.save()

                            walkin.delete()

                            login(request, user)
                            messages.success(
                                request,
                                f'✅ Account created and linked! '
                                f'Your past prescriptions have been '
                                f'transferred. '
                                f'Patient ID: {patient.patient_id}'
                            )
                            return redirect('dashboard')

                        except WalkInPatient.DoesNotExist:
                            messages.warning(
                                request,
                                '⚠️ Walk-in ID or phone did not match. '
                                'Account created without linking past '
                                'records.'
                            )

                    login(request, user)
                    messages.success(
                        request,
                        f'✅ Welcome {user.first_name}! '
                        f'Your Patient ID is: {patient.patient_id}'
                    )
                    return redirect('dashboard')

            except Exception as e:
                messages.error(request, f'Registration error: {e}')
        else:
            form = RegisterForm()
    else:
        form = RegisterForm()

    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('/admin/')
        return redirect('dashboard')

    if request.method == 'POST':
        username  = request.POST.get('username', '').strip().lower()
        password  = request.POST.get('password', '')
        user_type = request.POST.get('user_type', '')

        if not username or not password:
            messages.error(request, 'Enter both username and password')
            return render(request, 'auth/login.html')

        if not user_type:
            messages.error(request, 'Please select your role')
            return render(request, 'auth/login.html')

        user = authenticate(
            request, username=username, password=password
        )

        if user is not None:
            if user.is_superuser or user.is_staff:
                login(request, user)
                return redirect('/admin/')

            try:
                profile = user.profile
            except UserProfile.DoesNotExist:
                messages.error(request, 'Profile not found')
                return render(request, 'auth/login.html')

            if profile.user_type != user_type:
                messages.error(
                    request,
                    f'You are registered as '
                    f'{profile.get_user_type_display()}, '
                    f'not {user_type.title()}'
                )
                return render(request, 'auth/login.html')

            if user_type == 'doctor':
                try:
                    doctor = user.doctor
                    if doctor.verification_status == 'pending':
                        messages.warning(
                            request,
                            '⏳ Your account is pending admin '
                            'verification. You will be notified once '
                            'approved.'
                        )
                        return render(request, 'auth/login.html')
                    if doctor.verification_status == 'rejected':
                        messages.error(
                            request,
                            f'❌ Registration rejected. '
                            f'Reason: '
                            f'{doctor.rejection_reason or "Contact admin"}'
                        )
                        return render(request, 'auth/login.html')
                except Doctor.DoesNotExist:
                    messages.error(request, 'Doctor profile not found')
                    return render(request, 'auth/login.html')

            if user_type == 'pharmacy':
                try:
                    pharmacy = user.pharmacy
                    if pharmacy.verification_status == 'pending':
                        messages.warning(
                            request,
                            '⏳ Your pharmacy is pending admin '
                            'verification.'
                        )
                        return render(request, 'auth/login.html')
                    if pharmacy.verification_status == 'rejected':
                        messages.error(
                            request,
                            f'❌ Registration rejected. '
                            f'Reason: '
                            f'{pharmacy.rejection_reason or "Contact admin"}'
                        )
                        return render(request, 'auth/login.html')
                except Pharmacy.DoesNotExist:
                    messages.error(
                        request, 'Pharmacy profile not found'
                    )
                    return render(request, 'auth/login.html')

            login(request, user)
            messages.success(
                request, f'Welcome back, {user.first_name}! 👋'
            )
            return redirect('dashboard')

        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out successfully')
    return redirect('login')


# ==================== DASHBOARD ROUTER ====================

@login_required
def dashboard_view(request):
    if request.user.is_superuser or request.user.is_staff:
        return redirect('/admin/')
    try:
        user_type = request.user.profile.user_type
        routes = {
            'doctor':   'doctor_dashboard',
            'patient':  'patient_dashboard',
            'pharmacy': 'pharmacy_dashboard',
        }
        if user_type in routes:
            return redirect(routes[user_type])
        logout(request)
        return redirect('login')
    except Exception:
        logout(request)
        return redirect('login')


# ==================== DOCTOR VIEWS ====================

@login_required
def doctor_dashboard(request):
    if not check_role(request, 'doctor'):
        messages.error(request, 'Access denied')
        return redirect('dashboard')
    try:
        doctor        = request.user.doctor
        prescriptions = PrescriptionRecord.objects.filter(
            doctor=doctor
        )
        total  = prescriptions.count()
        filled = prescriptions.filter(is_filled=True).count()

        reg_patients    = prescriptions.filter(
            patient__isnull=False
        ).values('patient').distinct().count()
        walkin_patients = prescriptions.filter(
            walkin_patient__isnull=False
        ).values('walkin_patient').distinct().count()

        context = {
            'doctor'              : doctor,
            'total_prescriptions' : total,
            'pending_approvals'   : prescriptions.filter(
                is_filled=False, is_cancelled=False
            ).count(),
            'total_patients'      : reg_patients + walkin_patients,
            'success_rate'        : round(
                (filled / total * 100) if total > 0 else 0, 1
            ),
            'recent_prescriptions': prescriptions.order_by(
                '-created_at'
            )[:5],
        }
    except Exception:
        context = {
            'total_prescriptions': 0, 'pending_approvals': 0,
            'total_patients': 0, 'success_rate': 0,
            'recent_prescriptions': [],
        }
    return render(request, 'doctor_dashboard.html', context)


@login_required
def register_walkin_patient(request):
    if not check_role(request, 'doctor'):
        return JsonResponse(
            {'success': False, 'error': 'Access denied'}, status=403
        )

    if request.method == 'POST':
        import json
        try:
            data      = json.loads(request.body)
            full_name = data.get('full_name', '').strip()
            phone     = data.get('phone', '').strip()
            dob       = data.get('date_of_birth', '').strip()
            gender    = data.get('gender', 'Male').strip()
            blood     = data.get('blood_group', 'Unknown').strip()
            address   = data.get('address', '').strip()
            allergies = data.get('allergies', '').strip()

            if not full_name:
                return JsonResponse(
                    {'success': False, 'error': 'Full name is required'}
                )
            if not phone:
                return JsonResponse(
                    {'success': False, 'error': 'Phone number is required'}
                )
            if len(phone) != 10 or not phone.isdigit() or \
               phone[0] == '0':
                return JsonResponse({
                    'success': False,
                    'error':   'Phone must be 10 digits, '
                               'not starting with 0'
                })

            doctor = request.user.doctor

            walkin = WalkInPatient(
                full_name     = full_name,
                phone         = phone,
                gender        = gender,
                blood_group   = blood,
                address       = address,
                allergies     = allergies,
                registered_by = doctor,
            )
            if dob:
                from datetime import date
                try:
                    walkin.date_of_birth = date.fromisoformat(dob)
                except Exception:
                    pass

            walkin.save()
            walkin.refresh_from_db()

            return JsonResponse({
                'success'    : True,
                'patient_id' : walkin.patient_id,
                'full_name'  : walkin.full_name,
                'phone'      : walkin.phone,
                'dob'        : walkin.date_of_birth.strftime('%d %b %Y')
                               if walkin.date_of_birth else 'N/A',
                'gender'     : walkin.gender,
                'blood_group': walkin.blood_group,
                'age'        : walkin.age,
                'wallet'     : walkin.ethereum_address or '',
                'message'    : f'Patient registered! ID: {walkin.patient_id}'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return render(request, 'doctor/register_patient.html')


@login_required
def lookup_patient(request):
    if not check_role(request, 'doctor'):
        return JsonResponse(
            {'success': False, 'error': 'Access denied'}, status=403
        )

    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse(
            {'success': False,
             'error': 'Enter Patient ID or phone number'}
        )

    # Search WalkInPatient
    walkin = None
    if query.upper().startswith('P-'):
        walkin = WalkInPatient.objects.filter(
            patient_id__iexact=query
        ).first()
    else:
        walkin = WalkInPatient.objects.filter(phone=query).first()

    if walkin:
        rx_count = PrescriptionRecord.objects.filter(
            walkin_patient=walkin
        ).count()
        last_rx  = PrescriptionRecord.objects.filter(
            walkin_patient=walkin
        ).order_by('-created_at').first()

        return JsonResponse({
            'success'    : True,
            'type'       : 'walkin',
            'patient_id' : walkin.patient_id,
            'full_name'  : walkin.full_name,
            'phone'      : walkin.phone,
            'dob'        : walkin.date_of_birth.strftime('%d %b %Y')
                           if walkin.date_of_birth else 'N/A',
            'gender'     : walkin.gender,
            'blood_group': walkin.blood_group,
            'age'        : walkin.age,
            'allergies'  : walkin.allergies,
            'wallet'     : walkin.ethereum_address or '',
            'rx_count'   : rx_count,
            'last_visit' : last_rx.created_at.strftime('%d %b %Y')
                           if last_rx else 'First visit',
        })

    # Search Registered Patient
    reg_patient = None
    if query.upper().startswith('P-'):
        reg_patient = Patient.objects.filter(
            patient_id__iexact=query
        ).select_related('user', 'user__profile').first()
    else:
        try:
            profile     = UserProfile.objects.get(
                phone=query, user_type='patient'
            )
            reg_patient = profile.user.patient
        except Exception:
            pass

    if reg_patient:
        rx_count = PrescriptionRecord.objects.filter(
            patient=reg_patient
        ).count()
        last_rx  = PrescriptionRecord.objects.filter(
            patient=reg_patient
        ).order_by('-created_at').first()

        return JsonResponse({
            'success'    : True,
            'type'       : 'registered',
            'patient_id' : reg_patient.patient_id,
            'full_name'  : reg_patient.user.get_full_name(),
            'phone'      : reg_patient.phone,
            'dob'        : reg_patient.date_of_birth.strftime('%d %b %Y')
                           if reg_patient.date_of_birth else 'N/A',
            'gender'     : reg_patient.gender,
            'blood_group': reg_patient.blood_group,
            'age'        : reg_patient.age,
            'allergies'  : reg_patient.allergies,
            'wallet'     : reg_patient.wallet or '',
            'rx_count'   : rx_count,
            'last_visit' : last_rx.created_at.strftime('%d %b %Y')
                           if last_rx else 'First visit',
        })

    return JsonResponse({
        'success': False,
        'error':   f'No patient found with ID/Phone: {query}'
    })


@login_required
def view_patients(request):
    if not check_role(request, 'doctor'):
        return redirect('dashboard')

    try:
        doctor = request.user.doctor  # ✅ correct: related_name='doctor' in Doctor model
    except Doctor.DoesNotExist:
        return redirect('dashboard')

    prescriptions = PrescriptionRecord.objects.filter(
        doctor=doctor
    ).select_related('patient', 'patient__user', 'walkin_patient')

    seen = set()
    patient_data = []

    for rx in prescriptions.order_by('-created_at'):

        # ── Registered patient ──
        if rx.patient and rx.patient.id not in seen:
            seen.add(rx.patient.id)
            patient_data.append({
                'name':               rx.patient.user.get_full_name(),
                'avatar':             rx.patient.user.first_name[:1] + rx.patient.user.last_name[:1],
                'prescription_count': prescriptions.filter(patient=rx.patient).count(),
                'last_visit':         prescriptions.filter(patient=rx.patient).order_by('-created_at').first().created_at,
                'type':               'registered',
            })

        # ── Walk-in patient ──
        elif rx.walkin_patient:
            key = f'w_{rx.walkin_patient.id}'
            if key not in seen:
                seen.add(key)
                patient_data.append({
                    'name':               rx.walkin_patient.full_name,
                    'avatar':             rx.walkin_patient.full_name[:1],
                    'prescription_count': prescriptions.filter(walkin_patient=rx.walkin_patient).count(),
                    'last_visit':         prescriptions.filter(walkin_patient=rx.walkin_patient).order_by('-created_at').first().created_at,
                    'type':               'walkin',
                })

    return render(request, 'doctor/view_patients.html', {
        'patients':       patient_data,
        'total_patients': len(patient_data),
    })
    

@login_required
def prescription_history_doctor(request):
    if not check_role(request, 'doctor'):
        return redirect('dashboard')
    prescriptions = PrescriptionRecord.objects.filter(
        doctor__user=request.user
    ).order_by('-created_at')
    return render(request, 'doctor/prescription_history.html', {
        'prescriptions': prescriptions,
        'total_count'  : prescriptions.count()
    })


@login_required
def search_prescription_doctor(request):
    if not check_role(request, 'doctor'):
        return redirect('dashboard')
    query   = request.GET.get('q', '').strip()
    results = []
    if query:
        results = PrescriptionRecord.objects.filter(
            doctor__user=request.user
        ).filter(
            db_models.Q(
                prescription_id__icontains=query
            ) |
            db_models.Q(
                patient__user__first_name__icontains=query
            ) |
            db_models.Q(
                patient__user__last_name__icontains=query
            ) |
            db_models.Q(
                walkin_patient__full_name__icontains=query
            ) |
            db_models.Q(disease__icontains=query) |
            db_models.Q(drug__icontains=query)
        )
    return render(request, 'doctor/search_prescription.html', {
        'query'       : query,
        'results'     : results,
        'result_count': len(results) if results else 0
    })


@login_required
def doctor_analytics(request):
    if not check_role(request, 'doctor'):
        return redirect('dashboard')
    prescriptions = PrescriptionRecord.objects.filter(
        doctor__user=request.user
    )
    total   = prescriptions.count()
    filled  = prescriptions.filter(is_filled=True).count()
    pending = prescriptions.filter(
        is_filled=False, is_cancelled=False
    ).count()
    return render(request, 'doctor/analytics.html', {
        'total_prescriptions'  : total,
        'filled_prescriptions' : filled,
        'pending_prescriptions': pending,
        'total_patients'       : prescriptions.values(
            'patient'
        ).distinct().count(),
        'success_rate': round(
            (filled / total * 100) if total > 0 else 0, 1
        ),
        'pending_rate': round(
            (pending / total * 100) if total > 0 else 0, 1
        ),
    })


@login_required
def doctor_notifications(request):
    if not check_role(request, 'doctor'):
        return redirect('dashboard')
    recent_fills = PrescriptionRecord.objects.filter(
        doctor__user=request.user, is_filled=True
    ).order_by('-filled_at')[:10]
    return render(request, 'doctor/notifications.html', {
        'recent_fills': recent_fills
    })


@login_required
def update_profile_doctor(request):
    if not check_role(request, 'doctor'):
        return redirect('dashboard')
    if request.method == 'POST':
        request.user.first_name = request.POST.get(
            'first_name', ''
        ).strip()
        request.user.last_name  = request.POST.get(
            'last_name', ''
        ).strip()
        request.user.email      = request.POST.get('email', '').strip()
        request.user.save()
        profile       = request.user.profile
        profile.phone = request.POST.get('phone', '').strip()
        profile.save()
        try:
            doctor = request.user.doctor
            ln = request.POST.get('license_number', '').strip()
            if ln:
                doctor.license_number = ln
            doctor.specialization = request.POST.get(
                'specialization', doctor.specialization
            ).strip()
            doctor.hospital = request.POST.get('hospital', '').strip()
            doctor.save()
        except Exception:
            pass
        messages.success(request, 'Profile updated successfully')
        return redirect('doctor_dashboard')
    return render(request, 'doctor/update_profile.html')


# ==================== PATIENT VIEWS ====================

@login_required
def patient_dashboard(request):
    if not check_role(request, 'patient'):
        return redirect('dashboard')
    try:
        patient = request.user.patient

        # FIX Bug 1: Added select_related for correct field access
        prescriptions = PrescriptionRecord.objects.filter(
            patient=patient
        ).select_related(
            'doctor',
            'doctor__user',
            'walkin_patient'
        ).order_by('-created_at')

        total_count   = prescriptions.count()
        filled_count  = prescriptions.filter(is_filled=True).count()
        pending_count = prescriptions.filter(
            is_filled=False, is_cancelled=False
        ).count()

        # FIX Bug 3: Fetch notifications for bell icon
        notifications = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]

        unread_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()

        return render(request, 'patient_portal.html', {
            'patient'      : patient,
            'prescriptions': prescriptions,
            'total_count'  : total_count,
            'filled_count' : filled_count,
            'pending_count': pending_count,
            'notifications': notifications,
            'unread_count' : unread_count,
        })

    except Patient.DoesNotExist:
        return render(request, 'patient_portal.html', {
            'patient'      : None,
            'prescriptions': [],
            'total_count'  : 0,
            'filled_count' : 0,
            'pending_count': 0,
            'notifications': [],
            'unread_count' : 0,
        })
    except Exception as e:
        print(f'[PATIENT DASHBOARD] Error: {e}')
        return render(request, 'patient_portal.html', {
            'patient'      : None,
            'prescriptions': [],
            'total_count'  : 0,
            'filled_count' : 0,
            'pending_count': 0,
            'notifications': [],
            'unread_count' : 0,
        })


# FIX Bug 3: Mark single notification as read
@login_required
def mark_notification_read(request, notification_id):
    try:
        notif         = Notification.objects.get(
            id=notification_id, user=request.user
        )
        notif.is_read = True
        notif.save()
    except Notification.DoesNotExist:
        pass
    return redirect('patient_dashboard')


# FIX Bug 3: Mark all notifications as read
@login_required
def mark_all_notifications_read(request):
    Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)
    return redirect('patient_dashboard')


@login_required
def prescription_history_patient(request):
    if not check_role(request, 'patient'):
        return redirect('dashboard')
    try:
        patient       = request.user.patient
        prescriptions = PrescriptionRecord.objects.filter(
            patient=patient
        ).select_related(
            'doctor', 'doctor__user'
        ).order_by('-created_at')
    except Exception:
        prescriptions = []
    return render(request, 'patient/prescription_history.html', {
        'prescriptions': prescriptions,
        'total_count'  : len(prescriptions)
                         if prescriptions else 0
    })


@login_required
def generate_qr_patient(request, prescription_id):
    if not check_role(request, 'patient'):
        return redirect('dashboard')
    prescription = get_object_or_404(
        PrescriptionRecord,
        prescription_id=prescription_id,
        patient__user=request.user
    )
    return render(request, 'patient/generate_qr.html', {
        'prescription': prescription,
        'qr_data'     : prescription.prescription_id
    })


@login_required
def download_prescription_pdf(request, prescription_id):
    """Generate and download prescription as PDF with QR code"""
    if not check_role(request, 'patient'):
        return redirect('dashboard')

    try:
        rx = PrescriptionRecord.objects.select_related(
            'doctor',
            'doctor__user',
            'patient',
            'patient__user',
            'walkin_patient'
        ).get(
            prescription_id=prescription_id,
            patient__user=request.user
        )
    except PrescriptionRecord.DoesNotExist:
        messages.error(request, 'Prescription not found')
        return redirect('prescription_history_patient')

    # FIX Bug 2: QR encodes full verify URL not just prescription_id
    qr_b64 = None
    try:
        import qrcode
        import io
        import base64

        # Full URL so pharmacy can scan and open verify page directly
        verify_url = request.build_absolute_uri(
            f'/api/blockchain/get-prescription/{prescription_id}/'
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=6,
            border=2,
        )
        # FIX: was rx.prescription_id — now full verify URL
        qr.add_data(verify_url)
        qr.make(fit=True)

        qr_img    = qr.make_image(
            fill_color='#059669', back_color='white'
        )
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_b64 = base64.b64encode(
            qr_buffer.getvalue()
        ).decode('utf-8')
        print(
            f'[PDF] QR generated for {rx.prescription_id} '
            f'pointing to {verify_url}'
        )

    except ImportError as e:
        print(f'[PDF] QR library missing: {e}')
        print('Run: pip install qrcode[pil]')
    except Exception as e:
        print(f'[PDF] QR generation failed: {e}')

    # Render HTML template
    from django.template.loader import render_to_string
    html_content = render_to_string(
        'patient/prescription_pdf.html',
        {
            'rx'    : rx,
            'qr_b64': qr_b64,
        },
        request=request
    )

    # Generate PDF with WeasyPrint
    try:
        from weasyprint import HTML
        pdf = HTML(
            string=html_content,
            base_url=request.build_absolute_uri('/')
        ).write_pdf()

        response = HttpResponse(
            pdf, content_type='application/pdf'
        )
        response['Content-Disposition'] = (
            f'attachment; '
            f'filename="prescription-{rx.prescription_id}.pdf"'
        )
        print(
            f'[PDF] Generated successfully '
            f'for {rx.prescription_id}'
        )
        return response

    except ImportError:
        print('[PDF] WeasyPrint not installed.')
        print('Run: pip install weasyprint')
        return HttpResponse(html_content, content_type='text/html')

    except Exception as e:
        print(f'[PDF] WeasyPrint error: {e}')
        return HttpResponse(html_content, content_type='text/html')


@login_required
def medical_history_patient(request):
    if not check_role(request, 'patient'):
        return redirect('dashboard')
    prescriptions = PrescriptionRecord.objects.filter(
        patient__user=request.user
    ).select_related(
        'doctor', 'doctor__user'
    ).order_by('-created_at')
    return render(request, 'patient/medical_history.html', {
        'prescriptions': prescriptions
    })


@login_required
def my_doctors_patient(request):
    if not check_role(request, 'patient'):
        return redirect('dashboard')
    try:
        prescriptions = PrescriptionRecord.objects.filter(
            patient__user=request.user
        ).select_related('doctor', 'doctor__user')
        doctors = {}
        for rx in prescriptions:
            if not rx.doctor:
                continue
            did = rx.doctor.id
            if did not in doctors:
                doctors[did] = {
                    'doctor'            : rx.doctor,
                    'prescription_count': 0,
                    'last_visit'        : rx.created_at,
                }
            doctors[did]['prescription_count'] += 1
            if rx.created_at > doctors[did]['last_visit']:
                doctors[did]['last_visit'] = rx.created_at
    except Exception:
        doctors = {}
    return render(request, 'patient/my_doctors.html', {
        'doctors': list(doctors.values())
    })


@login_required
def patient_notifications(request):
    if not check_role(request, 'patient'):
        return redirect('dashboard')
    try:
        # FIX Bug 3: Show both new prescriptions AND filled
        notifications = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:20]
        recent_fills  = PrescriptionRecord.objects.filter(
            patient__user=request.user, is_filled=True
        ).order_by('-filled_at')[:20]
    except Exception:
        notifications = []
        recent_fills  = []
    return render(request, 'patient/notifications.html', {
        'notifications': notifications,
        'recent_fills' : recent_fills,
    })


@login_required
def update_profile_patient(request):
    if not check_role(request, 'patient'):
        return redirect('dashboard')
    if request.method == 'POST':
        request.user.first_name = request.POST.get(
            'first_name', ''
        ).strip()
        request.user.last_name  = request.POST.get(
            'last_name', ''
        ).strip()
        request.user.email      = request.POST.get('email', '').strip()
        request.user.save()
        profile       = request.user.profile
        profile.phone = request.POST.get('phone', '').strip()
        profile.save()
        try:
            patient             = request.user.patient
            patient.blood_group = request.POST.get(
                'blood_group', patient.blood_group
            )
            patient.allergies   = request.POST.get(
                'allergies', ''
            ).strip()
            patient.save()
        except Exception:
            pass
        messages.success(request, 'Profile updated')
        return redirect('patient_dashboard')
    return render(request, 'patient/update_profile.html')


# ==================== PHARMACY VIEWS ====================

@login_required
def pharmacy_dashboard(request):
    if not check_role(request, 'pharmacy'):
        return redirect('dashboard')
    try:
        pharmacy      = request.user.pharmacy
        today         = timezone.now().date()
        prescriptions = PrescriptionRecord.objects.filter(
            filled_by=pharmacy
        ).order_by('-filled_at')[:10]
        return render(request, 'pharmacy.html', {
            'pharmacy'    : pharmacy,
            'today_count' : PrescriptionRecord.objects.filter(
                filled_by=pharmacy,
                filled_at__date=today
            ).count(),
            'week_count'  : PrescriptionRecord.objects.filter(
                filled_by=pharmacy,
                filled_at__date__gte=today - timedelta(days=7)
            ).count(),
            'total_filled': PrescriptionRecord.objects.filter(
                filled_by=pharmacy, is_filled=True
            ).count(),
            'prescriptions': prescriptions,
        })
    except Exception:
        return render(request, 'pharmacy.html', {
            'today_count': 0, 'week_count': 0,
            'total_filled': 0, 'prescriptions': []
        })


@login_required
def dispensing_history_pharmacy(request):
    if not check_role(request, 'pharmacy'):
        return redirect('dashboard')
    try:
        pharmacy      = request.user.pharmacy
        prescriptions = PrescriptionRecord.objects.filter(
            filled_by=pharmacy, is_filled=True
        ).order_by('-filled_at')[:50]
    except Exception:
        prescriptions = []
    return render(request, 'pharmacy/dispensing_history.html', {
        'prescriptions': prescriptions
    })


@login_required
def daily_report_pharmacy(request):
    if not check_role(request, 'pharmacy'):
        return redirect('dashboard')
    try:
        pharmacy = request.user.pharmacy
        today    = timezone.now().date()
        context  = {
            'today_count': PrescriptionRecord.objects.filter(
                filled_by=pharmacy,
                filled_at__date=today
            ).count(),
            'week_count' : PrescriptionRecord.objects.filter(
                filled_by=pharmacy,
                filled_at__date__gte=today - timedelta(days=7)
            ).count(),
            'month_count': PrescriptionRecord.objects.filter(
                filled_by=pharmacy,
                filled_at__date__gte=today - timedelta(days=30)
            ).count(),
            'total_filled': PrescriptionRecord.objects.filter(  # ✅ ADD THIS
                filled_by=pharmacy, is_filled=True
            ).count(),
        }
    except Exception:
        context = {
            'today_count': 0, 'week_count': 0, 'month_count': 0, 'total_filled': 0
        }
    return render(request, 'pharmacy/daily_report.html', context)


@login_required
def pharmacy_analytics(request):
    if not check_role(request, 'pharmacy'):
        return redirect('dashboard')
    try:
        pharmacy = request.user.pharmacy
        today    = timezone.now().date()
        total    = PrescriptionRecord.objects.filter(
            filled_by=pharmacy, is_filled=True
        ).count()
        today_c  = PrescriptionRecord.objects.filter(
            filled_by=pharmacy,
            filled_at__date=today
        ).count()
        week_c   = PrescriptionRecord.objects.filter(
            filled_by=pharmacy,
            filled_at__date__gte=today - timedelta(days=7)
        ).count()
        month_c  = PrescriptionRecord.objects.filter(
            filled_by=pharmacy,
            filled_at__date__gte=today - timedelta(days=30)
        ).count()
        context  = {
            'today_count': today_c,
            'week_count' : week_c,
            'month_count': month_c,
            'total_filled': total,
            'today_rate' : round(
                (today_c / total * 100) if total > 0 else 0, 1
            ),
            'week_rate'  : round(
                (week_c / total * 100) if total > 0 else 0, 1
            ),
            'month_rate' : round(
                (month_c / total * 100) if total > 0 else 0, 1
            ),
        }
    except Exception:
        context = {
            'today_count': 0, 'week_count': 0,
            'month_count': 0, 'total_filled': 0,
            'today_rate': 0, 'week_rate': 0, 'month_rate': 0
        }
    return render(request, 'pharmacy/analytics.html', context)


@login_required
def pharmacy_alerts(request):
    if not check_role(request, 'pharmacy'):
        return redirect('dashboard')
    old_threshold     = timezone.now() - timedelta(days=30)
    old_prescriptions = PrescriptionRecord.objects.filter(
        is_filled=False,
        is_cancelled=False,
        created_at__lt=old_threshold
    )[:10]
    return render(request, 'pharmacy/alerts.html', {
        'old_prescriptions': old_prescriptions
    })


@login_required
def pharmacy_settings(request):
    if not check_role(request, 'pharmacy'):
        return redirect('dashboard')
    if request.method == 'POST':
        request.user.first_name = request.POST.get(
            'first_name', ''
        ).strip()
        request.user.last_name  = request.POST.get(
            'last_name', ''
        ).strip()
        request.user.email      = request.POST.get('email', '').strip()
        request.user.save()
        profile       = request.user.profile
        profile.phone = request.POST.get('phone', '').strip()
        profile.save()
        try:
            pharmacy = request.user.pharmacy
            pn       = request.POST.get('pharmacy_name', '').strip()
            if pn:
                pharmacy.pharmacy_name = pn
            pharmacy.address = request.POST.get('address', '').strip()
            pharmacy.save()
        except Exception:
            pass
        messages.success(request, 'Settings saved successfully')
        return redirect('pharmacy_dashboard')
    return render(request, 'pharmacy/settings.html', {
        'profile': request.user.profile
    })


@login_required
def pharmacy_inventory(request):
    if not check_role(request, 'pharmacy'):
        return redirect('dashboard')
    return render(request, 'pharmacy/inventory.html', {
        'message': 'Inventory management coming soon'
    })


@login_required
def qr_code_image(request, prescription_id):
    """Serves QR code as PNG — used by generate_qr.html"""
    try:
        rx = PrescriptionRecord.objects.get(
            prescription_id=prescription_id,
            patient__user=request.user
        )
    except PrescriptionRecord.DoesNotExist:
        from django.http import Http404
        raise Http404

    import qrcode
    import io

    # ✅ FIX: encode only the prescription ID
    # The pharmacy system looks up by ID, not by URL
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=6,
        border=2,
    )
    qr.add_data(prescription_id)   # ✅ was verify_url — now just ID
    qr.make(fit=True)
    qr_img = qr.make_image(
        fill_color='#059669', back_color='white'
    )

    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    buffer.seek(0)

    return HttpResponse(
        buffer.getvalue(), content_type='image/png'
    )