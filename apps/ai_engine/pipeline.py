"""
MedChain AI — Full 3-Stage Pipeline (FINAL FIXED VERSION)
==========================================================
Stage 1 : Symptoms        → Disease   (XGBoost + SHAP)
Stage 2 : Symptoms        → Drug      (Random Forest + LIME)
Stage 3 : Disease + Drug  → ADRs      (XGBoost Classifier Chain)

ALL FIXES APPLIED:
  1. X_train_bal → X_train (SMOTE removed from Stage 1)
  2. self.mlb removed — loaded but never used in inference
  3. feature_index dict — O(1) symptom lookup vs slow list.index()
  4. Singleton wrapped in try-except — server won't crash if pkl missing
  5. rules.py integrated — prevents medically impossible predictions
  6. Top 3 differentials returned — doctor sees alternatives
  7. Symptom count warnings — low symptom count downgrades tier
  8. Drug confidence warning — shown when drug confidence below 30%

Usage (Django view):
    from ai_engine.pipeline import pipeline
    result = pipeline.predict(['fever', 'chills', 'headache'])
"""

import os
import numpy as np
import joblib
import warnings
warnings.filterwarnings('ignore')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, 'models_trained')

# Import clinical validation rules
try:
    from .rules import apply_medical_rules
    RULES_AVAILABLE = True
except ImportError:
    try:
        from rules import apply_medical_rules
        RULES_AVAILABLE = True
    except ImportError:
        RULES_AVAILABLE = False

# ══════════════════════════════════════════════════════════════════
# TC_BRIDGE — WHO ATC therapeutic class mapping
# Used when drug is not found in medicine_dataset
# ══════════════════════════════════════════════════════════════════
TC_BRIDGE = {
    'antipyretics'        : 'pain analgesics',
    'antibiotics'         : 'anti infectives',
    'antiviral drugs'     : 'anti infectives',
    'antimalarial drugs'  : 'anti malarial',
    'antiretroviral drugs': 'anti infectives',
    'antihistamines'      : 'respiratory',
    'bronchodilators'     : 'respiratory',
    'corticosteroids'     : 'hormones',
    'levothyroxine'       : 'hormones',
    'methimazole'         : 'hormones',
    'dextrose'            : 'anti diabetic',
    'aspirin'             : 'pain analgesics',
    'ibuprofen'           : 'pain analgesics',
    'lisinopril'          : 'cardiac',
    'omeprazole'          : 'gastro intestinal',
    'sumatriptan'         : 'neuro cns',
    'nitrofurantoin'      : 'anti infectives',
    'acyclovir'           : 'anti infectives',
    'isoniazid'           : 'anti infectives',
    'chloroquine'         : 'anti malarial',
    'sofosbuvir'          : 'anti infectives',
    'entecavir'           : 'anti infectives',
    'fluconazole'         : 'anti infectives',
    'acetaminophen'       : 'pain analgesics',
    'ciprofloxacin'       : 'anti infectives',
    'prednisolone'        : 'hormones',
    'ursodiol'            : 'gastro intestinal',
    'diphenhydramine'     : 'respiratory',
    'levocetirizine'      : 'respiratory',
    'dulaglutide'         : 'anti diabetic',
    'clindamycin'         : 'anti infectives',
    'meclizine'           : 'neuro cns',
    'hydrocortisone'      : 'derma',
    'diosmin'             : 'cardiac',
    'mupirocin'           : 'derma',
    'isotretinoin'        : 'derma',
    'hydroxychloroquine'  : 'musculo skeletal',
    'cholestyramine'      : 'gastro intestinal',
    'amoxicillin'         : 'anti infectives',
    'montelukast'         : 'respiratory',
    'biktarvy'            : 'anti infectives',
    'dupilumab'           : 'derma',
    'entereg'             : 'gastro intestinal',
    'ranolazine'          : 'cardiac',
    'clopidogrel'         : 'cardiac',
    'ustekinumab'         : 'derma',
    'sodium hyaluronate'  : 'musculo skeletal',
    'insulin glargine'    : 'anti diabetic',
    'peginterferon alfa'  : 'anti infectives',
    'ribavirin'           : 'anti infectives',
    'supportive_care'     : 'gastro intestinal',
}

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

    def __init__(self):
        self._loaded = False
        self.load_models()

    # ──────────────────────────────────────────────────────────────
    # MODEL LOADING
    # ──────────────────────────────────────────────────────────────
    def load_models(self):
        try:
            # Stage 1
            self.xgb_disease   = joblib.load(f'{MODELS_DIR}/xgb_disease_model.pkl')
            self.le_disease    = joblib.load(f'{MODELS_DIR}/label_encoder.pkl')
            self.feature_names = joblib.load(f'{MODELS_DIR}/feature_names.pkl')
            self.severity_dict = joblib.load(f'{MODELS_DIR}/severity_dict.pkl')

            # FIX: O(1) dict lookup instead of slow list.index()
            self.feature_index = {
                name: i for i, name in enumerate(self.feature_names)
            }

            # Stage 2
            self.rf_drug    = joblib.load(f'{MODELS_DIR}/rf_drug_model.pkl')
            self.le_drug_s2 = joblib.load(f'{MODELS_DIR}/le_drug.pkl')

            # Stage 3
            # FIX: self.mlb removed — only needed during training not inference
            self.chain_model  = joblib.load(f'{MODELS_DIR}/chain_adr_model.pkl')
            self.le_drug_s3   = joblib.load(f'{MODELS_DIR}/le_adr_drug.pkl')
            self.le_tc        = joblib.load(f'{MODELS_DIR}/le_adr_tc.pkl')
            self.le_cc        = joblib.load(f'{MODELS_DIR}/le_adr_cc.pkl')
            self.le_ac        = joblib.load(f'{MODELS_DIR}/le_adr_ac.pkl')
            self.TOP_ADRS     = joblib.load(f'{MODELS_DIR}/stage3_adr_labels.pkl')
            self.ADR_SEVERITY = joblib.load(f'{MODELS_DIR}/adr_severity_dict.pkl')
            self.hf_map       = joblib.load(f'{MODELS_DIR}/hf_map.pkl')
            self.chain_order  = joblib.load(f'{MODELS_DIR}/chain_order.pkl')

            self._loaded = True
            print('✅ MedChain Pipeline — all models loaded successfully')

        except FileNotFoundError as e:
            print(f'❌ Pipeline — model file missing: {e}')
            raise
        except Exception as e:
            print(f'❌ Pipeline — load error: {e}')
            raise

    # ──────────────────────────────────────────────────────────────
    # FEATURE VECTOR BUILDER
    # ──────────────────────────────────────────────────────────────
    def _build_symptom_vector(self, symptom_list):
        """
        Convert symptom list → severity-weighted feature vector.
        FIX: Uses feature_index dict for O(1) lookup.
        """
        vec      = np.zeros(len(self.feature_names))
        found    = []
        notfound = []

        for sym in symptom_list:
            s = sym.strip().lower().replace(' ', '_')
            if s in self.feature_index:
                vec[self.feature_index[s]] = self.severity_dict.get(s, 1)
                found.append(s)
            else:
                notfound.append(s)

        return vec, found, notfound

    # ──────────────────────────────────────────────────────────────
    # STAGE 1 — Disease Prediction with Top 3 + Rules
    # ──────────────────────────────────────────────────────────────
    def predict_disease(self, symptom_list):
        vec, found, notfound = self._build_symptom_vector(symptom_list)

        pred_proba = self.xgb_disease.predict_proba([vec])[0]
        matched    = len(found)

        # Top 3 predictions
        top3_idx = pred_proba.argsort()[::-1][:3]
        top3 = []
        for i in top3_idx:
            conf = float(pred_proba[i])
            name = self.le_disease.inverse_transform([i])[0]

            # FIX: Downgrade tier based on symptom count
            if matched < 4:
                tier = 'LOW — enter more symptoms'
            elif matched < 6:
                tier = 'MEDIUM' if conf >= 0.70 else 'LOW'
            else:
                tier = 'HIGH' if conf >= 0.85 else \
                       'MEDIUM' if conf >= 0.70 else 'LOW'

            top3.append({
                'disease'        : name,
                'confidence'     : round(conf, 4),
                'confidence_pct' : f'{conf*100:.1f}%',
                'tier'           : tier,
            })

        # Apply clinical validation rules if available
        if RULES_AVAILABLE:
            rule_result = apply_medical_rules(
                predicted_disease = top3[0]['disease'],
                symptoms_entered  = found,
                top3_predictions  = top3[1:],
            )
            validated_disease = rule_result['disease']
            validated_entry   = next(
                (t for t in top3 if t['disease'] == validated_disease),
                top3[0]
            )
        else:
            rule_result       = {'rule_applied': False, 'warning': None}
            validated_disease = top3[0]['disease']
            validated_entry   = top3[0]

        # Top 5 symptoms by severity weight
        top5 = sorted(
            [(self.feature_names[i], float(vec[i]))
             for i in range(len(vec)) if vec[i] > 0],
            key=lambda x: x[1], reverse=True
        )[:5]

        return {
            'disease'         : validated_disease,
            'confidence'      : validated_entry['confidence'],
            'confidence_pct'  : validated_entry['confidence_pct'],
            'tier'            : validated_entry['tier'],
            'top5_symptoms'   : top5,
            'differentials'   : top3[1:],
            'symptoms_found'  : found,
            'symptoms_unknown': notfound,
            'rule_check'      : rule_result,
        }

    # ──────────────────────────────────────────────────────────────
    # STAGE 2 — Drug Recommendation
    # ──────────────────────────────────────────────────────────────
    def predict_drug(self, symptom_list):
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
    # STAGE 3 — ADR Detection
    # ──────────────────────────────────────────────────────────────
    def predict_adrs(self, disease_name, drug_name,
                     tc_val=None, cc_val=None,
                     hf_val='No', ac_val='unknown'):

        # Disease encoding — uses Stage 1 label encoder (same encoder)
        try:
            d_enc = self.le_disease.transform([disease_name.strip()])[0]
        except Exception:
            d_enc = 0

        # Drug encoding — with TC_BRIDGE fallback
        drug_lower = drug_name.lower().strip()
        try:
            dr_enc = self.le_drug_s3.transform([drug_lower])[0]
        except Exception:
            dr_enc = 0

        # Therapeutic class
        tc = (tc_val or TC_BRIDGE.get(drug_lower, 'unknown')).lower().strip()
        try:    tc_enc = self.le_tc.transform([tc])[0]
        except: tc_enc = 0

        # Chemical class
        cc = (cc_val or 'unknown').lower().strip()
        try:    cc_enc = self.le_cc.transform([cc])[0]
        except: cc_enc = 0

        # Habit forming
        hf_enc = self.hf_map.get(hf_val, 1)

        # Action class
        ac = ac_val.lower().strip()
        try:    ac_enc = self.le_ac.transform([ac])[0]
        except: ac_enc = 0

        x3    = np.array([[d_enc, dr_enc, tc_enc, cc_enc, hf_enc, ac_enc]])
        proba = self.chain_model.predict_proba(x3)[0]

        adr_results = []
        for adr, prob in sorted(zip(self.TOP_ADRS, proba),
                                 key=lambda x: x[1], reverse=True):
            sev_code  = self.ADR_SEVERITY.get(adr, 2)
            sev_label = SEVERITY_LABELS[sev_code]
            adr_results.append({
                'adr'            : adr,
                'probability'    : round(float(prob), 4),
                'probability_pct': f'{prob*100:.1f}%',
                'severity'       : sev_label,
                'severity_code'  : sev_code,
                'advice'         : SEVERITY_ADVICE[sev_label],
            })

        return adr_results

    # ──────────────────────────────────────────────────────────────
    # FULL PIPELINE — Main entry point for Django
    # ──────────────────────────────────────────────────────────────
    def predict(self, symptom_list, adr_threshold=0.05):
        if not self._loaded:
            return {'pipeline_status': 'error', 'error': 'Models not loaded'}

        if not symptom_list:
            return {'pipeline_status': 'error', 'error': 'symptom_list is empty'}

        try:
            # Stage 1
            stage1       = self.predict_disease(symptom_list)
            disease_name = stage1['disease']

            # Stage 2
            stage2    = self.predict_drug(symptom_list)
            drug_name = stage2['drug']

            # Stage 3
            all_adrs = self.predict_adrs(disease_name, drug_name)
            stage3   = [a for a in all_adrs
                        if a['probability'] >= adr_threshold]

            # Warnings
            warnings_list = []
            found_count   = len(stage1['symptoms_found'])

            if found_count < 4:
                warnings_list.append(
                    f'Only {found_count} symptoms recognized. '
                    f'Please enter at least 5 symptoms for reliable prediction.'
                )
            elif found_count < 6:
                warnings_list.append(
                    f'Only {found_count} symptoms entered. '
                    f'Adding more symptoms improves accuracy.'
                )

            if stage1.get('rule_check', {}).get('rule_applied'):
                w = stage1['rule_check'].get('warning')
                if w:
                    warnings_list.append(w)

            if stage2['confidence'] < 0.30:
                warnings_list.append(
                    f'Drug confidence is low ({stage2["confidence_pct"]}). '
                    f'Please review drug recommendation carefully.'
                )

            if 'LOW' in stage1['tier']:
                warnings_list.append(
                    'Low confidence prediction — verify diagnosis manually.'
                )

            # Summary
            severe_adrs = [a for a in stage3 if a['severity_code'] == 0]
            summary = {
                'disease'      : disease_name,
                'confidence'   : stage1['confidence_pct'],
                'tier'         : stage1['tier'],
                'drug'         : drug_name,
                'top_adrs'     : [f"{a['adr']} ({a['probability_pct']})"
                                  for a in stage3[:5]],
                'severe_adrs'  : [a['adr'] for a in severe_adrs],
                'adr_count'    : len(stage3),
                'warnings'     : warnings_list,
                'differentials': stage1['differentials'],
            }

            return {
                'stage1'         : stage1,
                'stage2'         : stage2,
                'stage3'         : stage3,
                'summary'        : summary,
                'warnings'       : warnings_list,
                'pipeline_status': 'success',
            }

        except Exception as e:
            return {'pipeline_status': 'error', 'error': str(e)}

    # ──────────────────────────────────────────────────────────────
    # UTILITIES
    # ──────────────────────────────────────────────────────────────
    def get_symptom_list(self):
        return sorted(self.feature_names)

    def get_disease_list(self):
        return sorted(self.le_disease.classes_.tolist())

    def health_check(self):
        try:
            result = self.predict([
                'chills', 'vomiting', 'high_fever',
                'sweating', 'headache', 'nausea',
                'diarrhoea', 'muscle_pain'
            ])
            ok = (result['pipeline_status'] == 'success' and
                  result['stage1']['disease'] == 'Malaria')
            return {
                'status'       : 'healthy' if ok else 'degraded',
                'disease_check': result['stage1']['disease'],
                'drug_check'   : result['stage2']['drug'],
                'adr_count'    : len(result['stage3']),
                'models_loaded': self._loaded,
                'rules_active' : RULES_AVAILABLE,
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}


# ══════════════════════════════════════════════════════════════════
# SINGLETON — FIX: wrapped in try-except
# Server starts even if models not yet trained
# ══════════════════════════════════════════════════════════════════
try:
    pipeline = MedChainPipeline()
except Exception as e:
    print(f'⚠️  Pipeline not loaded: {e}')
    print('   Train all 3 stages first then restart server')
    pipeline = None


# ══════════════════════════════════════════════════════════════════
# QUICK TEST — python pipeline.py
# ══════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('\n' + '='*65)
    print('  MedChain Pipeline FINAL — Test')
    print('='*65)

    p = MedChainPipeline()

    tests = [
        ('Malaria',      ['chills','vomiting','high_fever',
                          'sweating','headache','nausea',
                          'diarrhoea','muscle_pain']),
        ('Pneumonia',    ['chills','fatigue','cough','high_fever',
                          'breathlessness','sweating','phlegm',
                          'chest_pain','rusty_sputum']),
        ('Dengue',       ['skin_rash','chills','joint_pain',
                          'vomiting','high_fever','headache',
                          'nausea','pain_behind_the_eyes',
                          'red_spots_over_body']),
        ('Heart attack', ['chest_pain','breathlessness','sweating',
                          'fast_heart_rate','vomiting','anxiety',
                          'cold_hands_and_feets']),
        ('Diabetes',     ['increased_appetite','polyuria',
                          'excessive_hunger','fatigue',
                          'weight_loss','blurred_and_distorted_vision',
                          'restlessness','irregular_sugar_level']),
    ]

    print('\n✅ STANDARD TESTS:')
    all_passed = True
    for expected, symptoms in tests:
        result = p.predict(symptoms)
        got    = result['stage1']['disease']
        conf   = result['stage1']['confidence_pct']
        drug   = result['stage2']['drug']
        adrs   = len(result['stage3'])
        ok     = '✅' if got == expected else '❌'
        if got != expected:
            all_passed = False
        print(f'  {ok} Expected:{expected:<25} Got:{got:<25} {conf}')
        print(f'     Drug: {drug}  |  ADRs: {adrs}')
        if result['warnings']:
            for w in result['warnings']:
                print(f'     ⚠️  {w[:70]}')

    # Problem case test
    print('\n⚠️  PROBLEM CASE (skin_rash should NOT give Heart attack):')
    result = p.predict(['skin_rash','breathlessness','vomiting','cough'])
    got    = result['stage1']['disease']
    rule   = result['stage1']['rule_check']['rule_applied']
    print(f'  Final disease : {got}')
    print(f'  Rule applied  : {rule}')
    for w in result['warnings']:
        print(f'  ⚠️  {w[:80]}')

    print('\n' + '='*65)
    print(f'  All tests    : {"✅ PASSED" if all_passed else "❌ CHECK ABOVE"}')
    print(f'  Rules active : {RULES_AVAILABLE}')
    print(f'  Symptoms     : {len(p.get_symptom_list())}')
    print(f'  Diseases     : {len(p.get_disease_list())}')
    print('='*65)
