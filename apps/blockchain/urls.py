# apps/blockchain/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('store-prescription/', views.store_prescription_blockchain, name='store_prescription'),
    path('get-prescription/<str:prescription_id>/', views.get_prescription_blockchain, name='get_prescription'),
    path('fill-prescription/', views.fill_prescription_blockchain, name='fill_prescription'),
    path('status/', views.blockchain_status, name='blockchain_status'),
]