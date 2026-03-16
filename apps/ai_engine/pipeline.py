"""
MedChain AI — Full 3-Stage Pipeline
=====================================
Stage 1 : Symptoms        → Disease   (XGBoost + SMOTE + SHAP)
Stage 2 : Symptoms        → Drug      (Random Forest + LIME)
Stage 3 : Disease + Drug  → ADRs      (XGBoost Classifier Chain + Bootstrap Ensemble)

Usage (Django view):
    from ai_engine.pipeline import MedChainPipeline
    pipeline = MedChainPipeline()
    result   = pipeline.predict(['fever', 'chills', 'headache'])

Author  : MedChain AI Engine
"""

import os
import numpy as np
import joblib
import warnings
warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════════════════════
# PATH CONFIGURATION
# ══════════════════════════════════════════════════════════════════
# This file lives at: apps/ai_engine/pipeline.py
# Models live at    : apps/ai_engine/models_trained/
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR  = os.path.join(BASE_DIR, 'models_trained')


# ══════════════════════════════════════════════════════════════════
# TC_BRIDGE — Therapeutic class mapping for unknown drugs
# Derived from WHO ATC classification
# Used when a drug is not found in medicine_dataset
# ══════════════════════════════════════════════════════════════════
TC_BRIDGE = {
    'antipyretics'       : 'pain analgesics',
    'antibiotics'        : 'anti infectives',
    'antiviral drugs'    : 'anti infectives',
    'antimalarial drugs' : 'anti malarial',
    'antiretroviral drugs': 'anti infectives',
    'antihistamines'     : 'respiratory',
    'bronchodilators'    : 'respiratory',
    'corticosteroids'    : 'hormones',
    'levothyroxine'      : 'hormones',
    'methimazole'        : 'hormones',
    'dextrose'           : 'anti diabetic',
    'aspirin'            : 'pain analgesics',
    'ibuprofen'          : 'pain analgesics',
    'lisinopril'         : 'cardiac',
    'omeprazole'         : 'gastro intestinal',
    'sumatriptan'        : 'neuro cns',
    'nitrofurantoin'     : 'anti infectives',
    'acyclovir'          : 'anti infectives',
    'isoniazid'          : 'anti infectives',
    'chloroquine'        : 'anti malarial',
    'sofosbuvir'         : 'anti infectives',
    'entecavir'          : 'anti infectives',
    'fluconazole'        : 'anti infectives',
    'acetaminophen'      : 'pain analgesics',
    'ciprofloxacin'      : 'anti infectives',
    'prednisolone'       : 'hormones',
    'ursodiol'           : 'gastro intestinal',
    'diphenhydramine'    : 'respiratory',
    'levocetirizine'     : 'respiratory',
    'dulaglutide'        : 'anti diabetic',
    'clindamycin'        : 'anti infectives',
    'meclizine'          : 'neuro cns',
    'hydrocortisone'     : 'derma',
    'diosmin'            : 'cardiac',
    'mupirocin'          : 'derma',
    'isotretinoin'       : 'derma',
    'hydroxychloroquine' : 'musculo skeletal',
    'cholestyramine'     : 'gastro intestinal',
    'amoxicillin'        : 'anti infectives',
    'montelukast'        : 'respiratory',
    'biktarvy'           : 'anti infectives',
    'dupilumab'          : 'derma',
    'entereg'            : 'gastro intestinal',
    'ranolazine'         : 'cardiac',
    'clopidogrel'        : 'cardiac',
    'ustekinumab'        : 'derma',
    'sodium hyaluronate' : 'musculo skeletal',
    'insulin glargine'   : 'anti diabetic',
    'peginterferon alfa' : 'anti infectives',
    'ribavirin'          : 'anti infectives',
    'supportive_care'    : 'gastro intestinal',
}

# Severity labels + clinical advice (WHO/FDA standard)
SEVERITY_LABELS = {0: 'SEVERE', 1: 'MODERATE', 2: 'MILD'}
SEVERITY_ADVICE = {
    'SEVERE'  : 'STOP medication. Seek IMMEDIATE medical help.',
    'MODERATE': 'Monitor closely. Consult doctor promptly.',
    'MILD'    : 'Usually self-resolving. Inform doctor at next visit.',
}


# ══════════════════════════════════════════════════════════════════
# MedChainPipeline CLASS
# ══════════════════════════════════════════════════════════════════
class MedChainPipeline:
    """
    Full 3-stage AI pipeline for MedChain CDSS.

    Load once at Django startup (AppConfig.ready()):
        pipeline = MedChainPipeline()

    Then call per request:
        result = pipeline.predict(['fever', 'chills', 'headache'])
    """

    def __init__(self):
        self._loaded = False
        self.load_models()

    # ──────────────────────────────────────────────────────────────
    # MODEL LOADING
    # ──────────────────────────────────────────────────────────────
    def load_models(self):
        """Load all saved models from models_trained/"""
        try:
            # ── Stage 1 ──────────────────────────────────────────
            self.xgb_disease   = joblib.load(f'{MODELS_DIR}/xgb_disease_model.pkl')
            self.le_disease    = joblib.load(f'{MODELS_DIR}/label_encoder.pkl')
            self.feature_names = joblib.load(f'{MODELS_DIR}/feature_names.pkl')
            self.severity_dict = joblib.load(f'{MODELS_DIR}/severity_dict.pkl')

            # ── Stage 2 ──────────────────────────────────────────
            self.rf_drug       = joblib.load(f'{MODELS_DIR}/rf_drug_model.pkl')
            self.le_drug_s2    = joblib.load(f'{MODELS_DIR}/le_drug.pkl')

            # ── Stage 3 ──────────────────────────────────────────
            self.chain_model   = joblib.load(f'{MODELS_DIR}/chain_adr_model.pkl')
            self.le_drug_s3    = joblib.load(f'{MODELS_DIR}/le_adr_drug.pkl')
            self.le_tc         = joblib.load(f'{MODELS_DIR}/le_adr_tc.pkl')
            self.le_cc         = joblib.load(f'{MODELS_DIR}/le_adr_cc.pkl')
            self.le_ac         = joblib.load(f'{MODELS_DIR}/le_adr_ac.pkl')
            self.mlb           = joblib.load(f'{MODELS_DIR}/mlb_adr.pkl')
            self.TOP_ADRS      = joblib.load(f'{MODELS_DIR}/stage3_adr_labels.pkl')
            self.ADR_SEVERITY  = joblib.load(f'{MODELS_DIR}/adr_severity_dict.pkl')
            self.hf_map        = joblib.load(f'{MODELS_DIR}/hf_map.pkl')
            self.chain_order   = joblib.load(f'{MODELS_DIR}/chain_order.pkl')

            self._loaded = True
            print('✅ MedChain Pipeline — all models loaded successfully')

        except FileNotFoundError as e:
            print(f'❌ MedChain Pipeline — model file missing: {e}')
            print(f'   Expected models in: {MODELS_DIR}')
            raise
        except Exception as e:
            print(f'❌ MedChain Pipeline — load error: {e}')
            raise

    # ──────────────────────────────────────────────────────────────
    # FEATURE VECTOR BUILDER (shared by Stage 1 + 2)
    # ──────────────────────────────────────────────────────────────
    def _build_symptom_vector(self, symptom_list):
        """
        Convert symptom list → severity-weighted feature vector.
        Same logic as Stage 1 Cell 9 / Stage 2 Cell 6.
        """
        vec = np.zeros(len(self.feature_names))
        found    = []
        notfound = []

        for sym in symptom_list:
            s = sym.strip().lower().replace(' ', '_')
            if s in self.feature_names:
                vec[self.feature_names.index(s)] = \
                    self.severity_dict.get(s, 1)
                found.append(s)
            else:
                notfound.append(s)

        return vec, found, notfound

    # ──────────────────────────────────────────────────────────────
    # STAGE 1 — Symptoms → Disease
    # ──────────────────────────────────────────────────────────────
    def predict_disease(self, symptom_list):
        """
        Input : list of symptom strings
        Output: dict with disease, confidence, tier, top5_symptoms
        """
        vec, found, notfound = self._build_symptom_vector(symptom_list)

        pred_idx    = self.xgb_disease.predict([vec])[0]
        pred_proba  = self.xgb_disease.predict_proba([vec])[0]
        confidence  = float(pred_proba.max())
        disease     = self.le_disease.inverse_transform([pred_idx])[0]

        # Confidence tier
        if confidence >= 0.85:
            tier = 'HIGH'
        elif confidence >= 0.70:
            tier = 'MEDIUM'
        else:
            tier = 'LOW'

        # Top 5 contributing symptoms (by severity weight × presence)
        top5 = sorted(
            [(self.feature_names[i], float(vec[i]))
             for i in range(len(vec)) if vec[i] > 0],
            key=lambda x: x[1], reverse=True
        )[:5]

        return {
            'disease'         : disease,
            'confidence'      : round(confidence, 4),
            'confidence_pct'  : f'{confidence*100:.1f}%',
            'tier'            : tier,
            'top5_symptoms'   : top5,
            'symptoms_found'  : found,
            'symptoms_unknown': notfound,
        }

    # ──────────────────────────────────────────────────────────────
    # STAGE 2 — Symptoms → Drug
    # ──────────────────────────────────────────────────────────────
    def predict_drug(self, symptom_list):
        """
        Input : list of symptom strings
        Output: dict with drug name, confidence
        """
        vec, _, _ = self._build_symptom_vector(symptom_list)

        drug_code  = self.rf_drug.predict([vec])[0]
        drug_proba = self.rf_drug.predict_proba([vec])[0]
        confidence = float(drug_proba.max())
        drug_name  = self.le_drug_s2.inverse_transform([drug_code])[0]

        return {
            'drug'          : drug_name,
            'confidence'    : round(confidence, 4),
            'confidence_pct': f'{confidence*100:.1f}%',
        }

    # ──────────────────────────────────────────────────────────────
    # STAGE 3 — Disease + Drug → ADRs
    # ──────────────────────────────────────────────────────────────
    def predict_adrs(self, disease_name, drug_name,
                     tc_val=None, cc_val=None,
                     hf_val='No', ac_val='unknown'):
        """
        Input : disease name (str), drug name (str)
                optional: therapeutic class, chemical class,
                          habit forming, action class
        Output: list of ADR dicts sorted by probability
        """
        # Disease encoding
        try:
            d_enc = self.le_disease.transform(
                [disease_name.strip()])[0]
        except Exception:
            d_enc = 0

        # Drug encoding — with disease-mode fallback
        drug_lower = drug_name.lower().strip()
        try:
            dr_enc = self.le_drug_s3.transform([drug_lower])[0]
        except Exception:
            dr_enc = 0

        # Therapeutic class encoding
        tc = (tc_val or TC_BRIDGE.get(drug_lower, 'unknown')).lower().strip()
        try:
            tc_enc = self.le_tc.transform([tc])[0]
        except Exception:
            tc_enc = 0

        # Chemical class encoding
        cc = (cc_val or 'unknown').lower().strip()
        try:
            cc_enc = self.le_cc.transform([cc])[0]
        except Exception:
            cc_enc = 0

        # Habit forming encoding
        hf_enc = self.hf_map.get(hf_val, 1)

        # Action class encoding
        ac = ac_val.lower().strip()
        try:
            ac_enc = self.le_ac.transform([ac])[0]
        except Exception:
            ac_enc = 0

        # Predict
        x3    = np.array([[d_enc, dr_enc, tc_enc,
                           cc_enc, hf_enc, ac_enc]])
        proba = self.chain_model.predict_proba(x3)[0]

        # Build ADR result list
        adr_results = []
        for adr, prob in sorted(
                zip(self.TOP_ADRS, proba),
                key=lambda x: x[1], reverse=True):
            sev_code = self.ADR_SEVERITY.get(adr, 2)
            sev_label = SEVERITY_LABELS[sev_code]
            adr_results.append({
                'adr'         : adr,
                'probability' : round(float(prob), 4),
                'probability_pct': f'{prob*100:.1f}%',
                'severity'    : sev_label,
                'severity_code': sev_code,
                'advice'      : SEVERITY_ADVICE[sev_label],
            })

        return adr_results

    # ──────────────────────────────────────────────────────────────
    # FULL PIPELINE — Single entry point for Django
    # ──────────────────────────────────────────────────────────────
    def predict(self, symptom_list, adr_threshold=0.05):
        """
        Main method called by Django API view.

        Input:
            symptom_list  : list of symptom strings
                            e.g. ['fever', 'chills', 'headache']
            adr_threshold : minimum probability to include ADR
                            default 0.05 (5%)

        Output: dict with full pipeline result
        {
            'stage1': { disease, confidence, confidence_pct, tier, ... },
            'stage2': { drug, confidence, confidence_pct },
            'stage3': [ { adr, probability, severity, advice }, ... ],
            'summary': { disease, drug, top_adrs, severe_adrs },
            'pipeline_status': 'success' | 'partial' | 'error',
        }
        """
        if not self._loaded:
            return {
                'pipeline_status': 'error',
                'error': 'Models not loaded'
            }

        if not symptom_list or len(symptom_list) == 0:
            return {
                'pipeline_status': 'error',
                'error': 'symptom_list is empty'
            }

        try:
            # ── Stage 1 ──────────────────────────────
            stage1 = self.predict_disease(symptom_list)
            disease_name = stage1['disease']

            # ── Stage 2 ──────────────────────────────
            stage2 = self.predict_drug(symptom_list)
            drug_name = stage2['drug']

            # ── Stage 3 ──────────────────────────────
            all_adrs = self.predict_adrs(disease_name, drug_name)

            # Filter by threshold
            stage3 = [a for a in all_adrs
                      if a['probability'] >= adr_threshold]

            # ── Summary ──────────────────────────────
            severe_adrs = [a for a in stage3
                           if a['severity_code'] == 0]
            top_adrs    = stage3[:5]

            summary = {
                'disease'     : disease_name,
                'confidence'  : stage1['confidence_pct'],
                'drug'        : drug_name,
                'top_adrs'    : [
                    f"{a['adr']} ({a['probability_pct']})"
                    for a in top_adrs
                ],
                'severe_adrs' : [a['adr'] for a in severe_adrs],
                'adr_count'   : len(stage3),
            }

            return {
                'stage1'          : stage1,
                'stage2'          : stage2,
                'stage3'          : stage3,
                'summary'         : summary,
                'pipeline_status' : 'success',
            }

        except Exception as e:
            return {
                'pipeline_status': 'error',
                'error'          : str(e),
            }

    # ──────────────────────────────────────────────────────────────
    # UTILITY — Get all valid symptom names (for frontend dropdown)
    # ──────────────────────────────────────────────────────────────
    def get_symptom_list(self):
        """Returns all 132 valid symptom names."""
        return sorted(self.feature_names)

    # ──────────────────────────────────────────────────────────────
    # UTILITY — Get all disease names (for frontend display)
    # ──────────────────────────────────────────────────────────────
    def get_disease_list(self):
        """Returns all 41 disease names."""
        return sorted(self.le_disease.classes_.tolist())

    # ──────────────────────────────────────────────────────────────
    # UTILITY — Pipeline health check (for Django admin / monitoring)
    # ──────────────────────────────────────────────────────────────
    def health_check(self):
        """
        Quick self-test with known Malaria symptoms.
        Returns True if pipeline is working correctly.
        """
        try:
            result = self.predict([
                'chills', 'vomiting', 'high_fever',
                'sweating', 'headache', 'nausea',
                'diarrhoea', 'muscle_pain'
            ])
            ok = (
                result['pipeline_status'] == 'success' and
                result['stage1']['disease'] == 'Malaria' and
                len(result['stage3']) > 0
            )
            return {
                'status'         : 'healthy' if ok else 'degraded',
                'disease_check'  : result['stage1']['disease'],
                'drug_check'     : result['stage2']['drug'],
                'adr_count'      : len(result['stage3']),
                'models_loaded'  : self._loaded,
            }
        except Exception as e:
            return {
                'status': 'error',
                'error' : str(e),
            }


# ══════════════════════════════════════════════════════════════════
# SINGLETON — one instance reused across all Django requests
# Import this in Django views:
#   from ai_engine.pipeline import pipeline
# ══════════════════════════════════════════════════════════════════
pipeline = MedChainPipeline()


# ══════════════════════════════════════════════════════════════════
# QUICK TEST — run this file directly to verify pipeline works
# python pipeline.py
# ══════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('\n' + '='*65)
    print('  MedChain Pipeline — Direct Test')
    print('='*65)

    p = MedChainPipeline()

    tests = [
        {
            'name': 'Malaria',
            'symptoms': ['chills', 'vomiting', 'high_fever',
                         'sweating', 'headache', 'nausea',
                         'diarrhoea', 'muscle_pain']
        },
        {
            'name': 'Hypothyroidism',
            'symptoms': ['fatigue', 'weight_gain',
                         'cold_hands_and_feets', 'constipation',
                         'depression', 'enlarged_thyroid',
                         'brittle_nails', 'swollen_extremities']
        },
        {
            'name': 'Diabetes',
            'symptoms': ['increased_appetite', 'polyuria',
                         'excessive_hunger', 'fatigue',
                         'weight_loss', 'blurred_and_distorted_vision',
                         'restlessness', 'irregular_sugar_level']
        },
        {
            'name': 'Dengue',
            'symptoms': ['skin_rash', 'chills', 'joint_pain',
                         'vomiting', 'high_fever', 'headache',
                         'nausea', 'loss_of_appetite',
                         'pain_behind_the_eyes', 'muscle_pain']
        },
        {
            'name': 'Hypertension',
            'symptoms': ['headache', 'chest_pain', 'dizziness',
                         'loss_of_balance', 'lack_of_concentration']
        },
    ]

    all_passed = True
    for test in tests:
        result = p.predict(test['symptoms'])
        status = result['pipeline_status']
        if status == 'success':
            s1  = result['stage1']
            s2  = result['stage2']
            s3  = result['stage3']
            ok  = '✅' if s1['disease'] == test['name'] else '⚠️ '
            if s1['disease'] != test['name']:
                all_passed = False
            print(f"\n{ok} TEST — {test['name']}")
            print(f"   Stage 1 → Disease : {s1['disease']} "
                  f"({s1['confidence_pct']}) [{s1['tier']}]")
            print(f"   Stage 2 → Drug    : {s2['drug']} "
                  f"({s2['confidence_pct']})")
            print(f"   Stage 3 → ADRs    : {len(s3)} predicted")
            for adr in s3[:3]:
                print(f"     • {adr['adr']:<42} "
                      f"{adr['probability_pct']:>6}  "
                      f"[{adr['severity']}]")
        else:
            all_passed = False
            print(f"\n❌ TEST — {test['name']}: {result.get('error')}")

    print('\n' + '='*65)
    print(f"  Health Check : {p.health_check()['status'].upper()}")
    print(f"  All tests    : {'✅ PASSED' if all_passed else '⚠️  CHECK ABOVE'}")
    print(f"  Symptoms     : {len(p.get_symptom_list())} available")
    print(f"  Diseases     : {len(p.get_disease_list())} covered")
    print('='*65)
    