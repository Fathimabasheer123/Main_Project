# apps/prescriptions/urls.py
from django.urls import path
from . import views

urlpatterns = [

    # ── Public ───────────────────────────────────────────────
    path('',          views.index,         name='home'),
    path('register/', views.register_view, name='register'),
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),

    # ── Dashboard router ─────────────────────────────────────
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # ── Doctor ───────────────────────────────────────────────
    path('dashboard/doctor/',
         views.doctor_dashboard,
         name='doctor_dashboard'),

    path('doctor/register-patient/',
         views.register_walkin_patient,
         name='register_walkin_patient'),

    path('doctor/lookup-patient/',
         views.lookup_patient,
         name='lookup_patient'),

    path('doctor/patients/',
         views.view_patients,
         name='view_patients'),

    path('doctor/history/',
         views.prescription_history_doctor,
         name='prescription_history_doctor'),

    path('doctor/search/',
         views.search_prescription_doctor,
         name='search_prescription_doctor'),

    path('doctor/analytics/',
         views.doctor_analytics,
         name='doctor_analytics'),

    path('doctor/notifications/',
         views.doctor_notifications,
         name='doctor_notifications'),

    path('doctor/profile/',
         views.update_profile_doctor,
         name='update_profile_doctor'),

    # ── Patient ──────────────────────────────────────────────
    path('dashboard/patient/',
         views.patient_dashboard,
         name='patient_dashboard'),

    path('patient/history/',
         views.prescription_history_patient,
         name='prescription_history_patient'),

    path('patient/qr-image/<str:prescription_id>/',
         views.qr_code_image,
         name='qr_code_image'),

    path('patient/download/<str:prescription_id>/',
         views.download_prescription_pdf,
         name='download_prescription_pdf'),

    path('patient/medical-history/',
         views.medical_history_patient,
         name='medical_history_patient'),

    path('patient/doctors/',
         views.my_doctors_patient,
         name='my_doctors_patient'),

    path('patient/notifications/',
         views.patient_notifications,
         name='patient_notifications'),

    path('patient/profile/',
         views.update_profile_patient,
         name='update_profile_patient'),

    # FIX Bug 3: Notification read/unread URLs
    path('patient/notifications/read/<int:notification_id>/',
         views.mark_notification_read,
         name='mark_notification_read'),

    path('patient/notifications/read-all/',
         views.mark_all_notifications_read,
         name='mark_all_notifications_read'),

    # ── Pharmacy ─────────────────────────────────────────────
    path('dashboard/pharmacy/',
         views.pharmacy_dashboard,
         name='pharmacy_dashboard'),

    path('pharmacy/history/',
         views.dispensing_history_pharmacy,
         name='dispensing_history_pharmacy'),

    path('pharmacy/report/',
         views.daily_report_pharmacy,
         name='daily_report_pharmacy'),

    path('pharmacy/analytics/',
         views.pharmacy_analytics,
         name='pharmacy_analytics'),

    path('pharmacy/alerts/',
         views.pharmacy_alerts,
         name='pharmacy_alerts'),

    path('pharmacy/settings/',
         views.pharmacy_settings,
         name='pharmacy_settings'),

    path('pharmacy/inventory/',
         views.pharmacy_inventory,
         name='pharmacy_inventory'),
]
