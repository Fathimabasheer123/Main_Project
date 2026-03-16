# apps/prescriptions/validators.py

import re
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime

def validate_ethereum_address(address):
    """Validate Ethereum address format"""
    if not address:
        raise ValidationError('Ethereum address is required')
    
    # Check if it starts with 0x and has 40 hex characters
    if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
        raise ValidationError('Invalid Ethereum address format. Must be 0x + 40 hex characters')
    
    return address

def validate_patient_age(age):
    """Validate patient age is reasonable"""
    try:
        age = int(age)
        if age < 0 or age > 150:
            raise ValidationError('Age must be between 0 and 150')
        return age
    except (ValueError, TypeError):
        raise ValidationError('Age must be a valid number')

def validate_patient_name(name):
    """Validate patient name"""
    if not name or len(name.strip()) < 2:
        raise ValidationError('Patient name must be at least 2 characters')
    
    if not re.match(r'^[a-zA-Z\s\.\-]+$', name):
        raise ValidationError('Patient name can only contain letters, spaces, dots and hyphens')
    
    return name.strip().title()

def validate_disease(disease):
    """Validate disease/diagnosis"""
    if not disease or len(disease.strip()) < 3:
        raise ValidationError('Diagnosis must be at least 3 characters')
    return disease.strip()

def validate_medicine_name(medicine):
    """Validate medicine name"""
    if not medicine or len(medicine.strip()) < 2:
        raise ValidationError('Medicine name must be at least 2 characters')
    return medicine.strip()

def validate_dosage(dosage):
    """Validate dosage format - more flexible"""
    if not dosage or len(dosage.strip()) < 1:
        raise ValidationError('Dosage is required')

    dosage = dosage.lower().strip()

    # Accept common medical dosage formats
    valid_patterns = [
        r'^\d+(\.\d+)?\s*(mg|mcg|g|ml|l|iu|units?)$',
        r'^\d+(\.\d+)?\s*mg/kg$',
        r'^\d+(\.\d+)?\s*%$',
        r'^\d+(\.\d+)?\s*tablets?$',
        r'^\d+(\.\d+)?\s*capsules?$',
        r'^\d+(\.\d+)?\s*injections?$',
        r'^\d+(\.\d+)?\s*puffs?$',
        r'^\d+(\.\d+)?\s*drops?$',
        r'^\d+(\.\d+)?\s*sachets?$',
        r'^\d+(\.\d+)?\s*suppositories?$',
    ]

    import re
    for pattern in valid_patterns:
        if re.match(pattern, dosage):
            return dosage

    raise ValidationError(
        'Invalid dosage. Use formats like: '
        '"500mg", "10ml", "1 tablet", "2 capsules", "5mg/kg"'
    )
def validate_frequency(frequency):
    """Validate frequency"""
    valid_frequencies = [
        'once daily', 'twice daily', 'three times daily', 'four times daily',
        'every 4 hours', 'every 6 hours', 'every 8 hours', 'every 12 hours',
        'as needed', 'prn', 'before meals', 'after meals', 'with meals',
        'at bedtime', 'in the morning', 'in the evening', 'every morning',
        'every night', 'twice a week', 'once a week'
    ]
    
    frequency = frequency.lower().strip()
    if frequency not in valid_frequencies:
        raise ValidationError(f'Invalid frequency. Choose from: once daily, twice daily, etc.')
    
    return frequency

def validate_duration(duration):
    """Validate duration format"""
    valid_patterns = [
        r'^\d+\s*days?$',
        r'^\d+\s*weeks?$',
        r'^\d+\s*months?$',
        r'^as\s+needed$',
        r'^single\s+dose$',
        r'^for\s+\d+\s*days?$',
    ]
    
    duration = duration.lower().strip()
    for pattern in valid_patterns:
        if re.match(pattern, duration):
            return duration
    
    raise ValidationError('Invalid duration. Use e.g., "7 days", "2 weeks", "1 month", "as needed"')

def validate_symptoms(symptoms):
    """Validate symptoms description"""
    if not symptoms or len(symptoms.strip()) < 10:
        raise ValidationError('Please describe symptoms in detail (minimum 10 characters)')
    return symptoms.strip()

def validate_instructions(instructions):
    """Validate instructions"""
    if not instructions or len(instructions.strip()) < 5:
        raise ValidationError('Instructions must be at least 5 characters')
    return instructions.strip()

def validate_phone(phone):
    """Validate phone number"""
    if phone:
        phone = re.sub(r'[\s\-\(\)\+]', '', phone)
        if phone and not phone.isdigit():
            raise ValidationError('Phone number must contain only digits')
        if phone and len(phone) != 10:
            raise ValidationError('Phone number must be exactly 10 digits')
        if phone and phone[0] == '0':
            raise ValidationError('Phone number cannot start with 0')
    return phone