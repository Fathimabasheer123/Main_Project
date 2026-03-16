# apps/prescriptions/serializers.py

from rest_framework import serializers
from .validators import (
    validate_ethereum_address, validate_patient_age,
    validate_patient_name, validate_disease,
    validate_medicine_name, validate_dosage,
    validate_frequency, validate_duration,
    validate_symptoms, validate_instructions, validate_phone
)


class PrescriptionSerializer(serializers.Serializer):
    """
    Used for API validation when prescriptions are
    submitted via REST API (not the HTML form).
    HTML form goes through blockchain_views.py directly.
    """

    # Patient Information
    patient_name = serializers.CharField(
        validators=[validate_patient_name]
    )
    patient_address = serializers.CharField(
        validators=[validate_ethereum_address]
    )
    patient_age = serializers.IntegerField(
        validators=[validate_patient_age]
    )
    patient_gender = serializers.ChoiceField(
        choices=['Male', 'Female', 'Other']
    )
    patient_phone = serializers.CharField(
        required=False, allow_blank=True,
        validators=[validate_phone]
    )

    # Medical
    symptoms = serializers.CharField(
        validators=[validate_symptoms]
    )
    disease = serializers.CharField(
        validators=[validate_disease]
    )
    disease_code = serializers.CharField(
        required=False, allow_blank=True, max_length=20
    )

    # Prescription
    medicine_name = serializers.CharField(
        validators=[validate_medicine_name]
    )
    generic_name = serializers.CharField(
        required=False, allow_blank=True, max_length=200
    )
    dosage = serializers.CharField(
        validators=[validate_dosage]
    )
    frequency = serializers.CharField(
        validators=[validate_frequency]
    )
    duration = serializers.CharField(
        validators=[validate_duration]
    )
    instructions = serializers.CharField(
        validators=[validate_instructions]
    )
    side_effects = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )
    followup_date = serializers.DateField(
        required=False, allow_null=True
    )
    tests = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )

    def validate(self, data):
        errors = {}
        age = data.get('patient_age', 999)
        medicine = data.get('medicine_name', '').lower()

        age_restricted = {
            'aspirin': 16, 'codeine': 18, 'tramadol': 18,
            'diazepam': 18, 'tetracycline': 12, 'ibuprofen': 12,
        }

        # FIX — collect all matching errors, not just last
        age_errors = []
        for med, min_age in age_restricted.items():
            if med in medicine and age < min_age:
                age_errors.append(
                    f'{med.title()} not recommended under {min_age} years'
                )
        if age_errors:
            errors['medicine_name'] = age_errors[0]

        if data.get('followup_date'):
            from django.utils import timezone
            if data['followup_date'] < timezone.now().date():
                errors['followup_date'] = (
                    'Follow-up date must be in the future'
                )

        if errors:
            raise serializers.ValidationError(errors)

        return data

    def create(self, validated_data):
        """Format data for blockchain storage"""
        drug_info = (
            f"{validated_data['medicine_name']} "
            f"{validated_data['dosage']} - "
            f"{validated_data['frequency']} for "
            f"{validated_data['duration']}. "
            f"{validated_data['instructions']}"
        )

        return {
            'patient_address': validated_data['patient_address'],
            'disease': validated_data['disease'],
            'drug': drug_info,
            'adverse_effects': validated_data.get(
                'side_effects', 'None noted'
            ),
            'dosage': validated_data['dosage'],
            'frequency': validated_data['frequency'],
            'duration': validated_data['duration'],
            'instructions': validated_data['instructions'],
            'patient_data': {
                'name': validated_data['patient_name'],
                'age': validated_data['patient_age'],
                'gender': validated_data['patient_gender'],
                'phone': validated_data.get('patient_phone', ''),
                'symptoms': validated_data['symptoms'],
                'notes': validated_data.get('notes', ''),
                'followup': str(
                    validated_data.get('followup_date', '')
                ),
                'tests': validated_data.get('tests', '')
            }
        }