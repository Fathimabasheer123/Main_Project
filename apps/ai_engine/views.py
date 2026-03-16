# apps/ai_engine/views.py

import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods


@login_required
@require_http_methods(["POST"])
def ai_predict(request):
    """
    Doctor enters symptoms → AI predicts disease, drug, ADRs
    Returns suggestions for doctor to review
    """
    try:
        data     = json.loads(request.body)
        symptoms = data.get('symptoms', [])

        if not symptoms:
            return JsonResponse({
                'success': False,
                'error':   'No symptoms provided'
            }, status=400)

        # Clean symptoms
        if isinstance(symptoms, str):
            symptoms = [
                s.strip() for s in symptoms.split(',')
                if s.strip()
            ]

        # Get pipeline
        from django.conf import settings
        pipeline = getattr(settings, 'AI_PIPELINE', None)

        if pipeline is None:
            # Try loading directly
            try:
                from apps.ai_engine.pipeline import MedChainPipeline
                pipeline = MedChainPipeline()
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error':   f'AI Pipeline unavailable: {str(e)}'
                }, status=503)

        # Run prediction
        result = pipeline.predict(symptoms)

        if result['pipeline_status'] == 'error':
            return JsonResponse({
                'success': False,
                'error':   result.get('error', 'Prediction failed')
            }, status=500)

        s1 = result['stage1']
        s2 = result['stage2']
        s3 = result['stage3']

        # Format ADRs for frontend
        adrs = []
        for adr in s3[:5]:
            adrs.append({
                'name':        adr['adr'],
                'probability': adr['probability_pct'],
                'severity':    adr['severity'],
                'advice':      adr['advice'],
            })

        return JsonResponse({
            'success': True,
            'disease': {
                'name':       s1['disease'],
                'confidence': s1['confidence_pct'],
                'tier':       s1['tier'],
            },
            'drug': {
                'name':       s2['drug'],
                'confidence': s2['confidence_pct'],
            },
            'adrs':           adrs,
            'severe_adrs':    result['summary']['severe_adrs'],
            'symptoms_found': s1.get('symptoms_found', []),
            'symptoms_missed': s1.get('symptoms_not_found', []),
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': 'Invalid JSON'},
            status=400
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=500
        )


@login_required
@require_http_methods(["GET"])
def get_symptoms_list(request):
    """Returns all valid symptom names for autocomplete"""
    try:
        from django.conf import settings
        pipeline = getattr(settings, 'AI_PIPELINE', None)
        if pipeline is None:
            from apps.ai_engine.pipeline import MedChainPipeline
            pipeline = MedChainPipeline()
        symptoms = pipeline.get_symptom_list()
        return JsonResponse({'success': True, 'symptoms': symptoms})
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=500
        )

@login_required
@require_http_methods(["GET"])
def get_diseases_list(request):
    try:
        from django.conf import settings
        pipeline = getattr(settings, 'AI_PIPELINE', None)
        if pipeline is None:
            from apps.ai_engine.pipeline import MedChainPipeline
            pipeline = MedChainPipeline()
        diseases = pipeline.get_disease_list()
        return JsonResponse({'success': True, 'diseases': diseases})
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=500
        )


@login_required
@require_http_methods(["GET"])
def health_check(request):
    try:
        from django.conf import settings
        pipeline = getattr(settings, 'AI_PIPELINE', None)
        if pipeline is None:
            from apps.ai_engine.pipeline import MedChainPipeline
            pipeline = MedChainPipeline()
        result = pipeline.health_check()
        return JsonResponse({'success': True, 'status': result})
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=500
        )