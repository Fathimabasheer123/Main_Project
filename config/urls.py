from django.contrib import admin
from django.urls import path, include
from apps.prescriptions import views

urlpatterns = [
    path('', views.index, name='home'),
    path('doctor/', views.doctor_dashboard, name='doctor'),
    path('patient/', views.patient_portal, name='patient'),
    path('pharmacy/', views.pharmacy_interface, name='pharmacy'),
    path('admin/', admin.site.urls),
    path('api/blockchain/', include('apps.blockchain.urls')),
    path('api/prescriptions/', include('apps.prescriptions.urls')),
]