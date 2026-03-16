# apps/ai_engine/apps.py

from django.apps import AppConfig


class AiEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai_engine'

    def ready(self):
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            return
        try:
            from apps.ai_engine.pipeline import MedChainPipeline
            from django.conf import settings
            settings.AI_PIPELINE = MedChainPipeline()
            print('✅ AI Pipeline loaded successfully')
        except Exception as e:
            print(f'⚠️  AI Pipeline failed to load: {e}')
            print('    AI features will be unavailable')