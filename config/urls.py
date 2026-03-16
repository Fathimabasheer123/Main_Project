# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # All blockchain API endpoints
    path('api/blockchain/', include('apps.blockchain.urls')),

    # All page views — auth, dashboards, prescriptions
    path('', include('apps.prescriptions.urls')),
    path('api/ai/', include('apps.ai_engine.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT
    )