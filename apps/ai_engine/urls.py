# apps/ai_engine/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('predict/',  views.ai_predict,       name='ai_predict'),
    path('symptoms/', views.get_symptoms_list, name='ai_symptoms'),
]