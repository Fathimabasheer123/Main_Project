# apps/prescriptions/migrations/0003_walkinpatient_and_more.py
# Generated for MedChain — depends on your actual 0002

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('prescriptions', '0002_alter_patient_options_alter_pharmacy_options_and_more'),
    ]

    operations = [

        # ── 1. Add patient_id to Patient (blank first, then unique) ─
        # Must add as blank=True first because existing rows need a value
        migrations.AddField(
            model_name='patient',
            name='patient_id',
            field=models.CharField(
                blank=True, default='', max_length=20,
                help_text='System-generated Patient ID (P-XXXXX)'
            ),
        ),

        # ── 2. Add gender to Patient ──────────────────────────────
        # Already blank=True so no default prompt
        migrations.AddField(
            model_name='patient',
            name='gender',
            field=models.CharField(
                blank=True, default='',
                choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
                max_length=10
            ),
        ),

        # ── 3. Add address to Patient ─────────────────────────────
        migrations.AddField(
            model_name='patient',
            name='address',
            field=models.TextField(blank=True, default=''),
        ),

        # ── 4. Add Unknown to Patient blood_group choices ─────────
        # Old 0001 had no 'Unknown' choice — add it
        migrations.AlterField(
            model_name='patient',
            name='blood_group',
            field=models.CharField(
                blank=True, default='Unknown',
                choices=[
                    ('A+', 'A+'), ('A-', 'A-'),
                    ('B+', 'B+'), ('B-', 'B-'),
                    ('AB+', 'AB+'), ('AB-', 'AB-'),
                    ('O+', 'O+'), ('O-', 'O-'),
                    ('Unknown', 'Unknown'),
                ],
                max_length=10
            ),
        ),

        # ── 5. Create WalkInPatient model ─────────────────────────
        migrations.CreateModel(
            name='WalkInPatient',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('patient_id', models.CharField(
                    max_length=20, unique=True,
                    help_text='Auto-generated P-XXXXX ID'
                )),
                ('full_name', models.CharField(max_length=200)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('gender', models.CharField(
                    choices=[
                        ('Male', 'Male'),
                        ('Female', 'Female'),
                        ('Other', 'Other'),
                    ],
                    default='Male', max_length=10
                )),
                ('phone', models.CharField(max_length=15)),
                ('blood_group', models.CharField(
                    choices=[
                        ('A+', 'A+'), ('A-', 'A-'),
                        ('B+', 'B+'), ('B-', 'B-'),
                        ('AB+', 'AB+'), ('AB-', 'AB-'),
                        ('O+', 'O+'), ('O-', 'O-'),
                        ('Unknown', 'Unknown'),
                    ],
                    default='Unknown', max_length=10
                )),
                ('address', models.TextField(blank=True, default='')),
                ('allergies', models.TextField(blank=True, default='')),
                ('ethereum_address', models.CharField(
                    blank=True, max_length=42, null=True
                )),
                ('registered_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registered_patients',
                    to='prescriptions.doctor'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Walk-in Patient',
                'verbose_name_plural': 'Walk-in Patients',
                'ordering': ['-created_at'],
            },
        ),

        # ── 6. Add walkin_patient FK to PrescriptionRecord ────────
        migrations.AddField(
            model_name='prescriptionrecord',
            name='walkin_patient',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='prescriptions',
                to='prescriptions.walkinpatient'
            ),
        ),

        # ── 7. NOTE: license_number stays blank=True, default='' ──
        # Your 0002 already set it to blank=True default=''.
        # The new models.py removes blank=True but we intentionally
        # do NOT enforce that here — existing rows would break.
        # The required validation is handled in views.py and forms.py,
        # not at the DB level. This avoids a one-off default prompt.
    ]