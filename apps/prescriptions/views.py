from django.shortcuts import render

def index(request):
    return render(request, 'index.html')

def doctor_dashboard(request):
    return render(request, 'doctor_dashboard.html')

def patient_portal(request):
    return render(request, 'patient_portal.html')

def pharmacy_interface(request):
    return render(request, 'pharmacy.html')