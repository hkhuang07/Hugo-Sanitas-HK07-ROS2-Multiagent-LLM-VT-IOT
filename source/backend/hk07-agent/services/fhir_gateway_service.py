"""
FhirGatewayService — Phase 20 HL7 FHIR Standard EHR Gateway

Translates clinical entries and vital signs from the Blackboard shared memory
into standard HL7 FHIR JSON resources (Observation and Condition) using official
LOINC and SNOMED-CT system codings.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from services.blackboard_service import ClinicalEntry

class FhirGatewayService:
    @staticmethod
    def to_fhir_observations(entry: ClinicalEntry) -> List[Dict[str, Any]]:
        """
        Translates numerical vitals from a ClinicalEntry into individual FHIR Observation resources
        packaged with proper LOINC and UCUM codes.
        """
        observations = []
        vitals = entry.vitals or {}
        timestamp = entry.timestamp or (datetime.utcnow().isoformat() + "Z")
        
        # 1. Heart Rate
        if "heartRate" in vitals or "hr" in vitals:
            hr_val = vitals.get("heartRate") or vitals.get("hr", 0)
            observations.append({
                "resourceType": "Observation",
                "id": f"obs-heartrate-{uuid.uuid4().hex[:12]}",
                "status": "final",
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "vital-signs",
                                "display": "Vital Signs"
                            }
                        ]
                    }
                ],
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8867-4",
                            "display": "Heart rate"
                        }
                    ],
                    "text": "Heart rate"
                },
                "subject": {
                    "reference": "Patient/hk07-patient",
                    "display": "HK-07 Patient"
                },
                "effectiveDateTime": timestamp,
                "valueQuantity": {
                    "value": float(hr_val),
                    "unit": "beats/minute",
                    "system": "http://unitsofmeasure.org",
                    "code": "/min"
                }
            })
            
        # 2. Oxygen Saturation (SpO2)
        if "spo2" in vitals:
            spo2_val = vitals.get("spo2", 99.0)
            observations.append({
                "resourceType": "Observation",
                "id": f"obs-spo2-{uuid.uuid4().hex[:12]}",
                "status": "final",
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "vital-signs",
                                "display": "Vital Signs"
                            }
                        ]
                    }
                ],
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "2708-6",
                            "display": "Oxygen saturation in Arterial blood by Pulse oximetry"
                        }
                    ],
                    "text": "Oxygen saturation"
                },
                "subject": {
                    "reference": "Patient/hk07-patient",
                    "display": "HK-07 Patient"
                },
                "effectiveDateTime": timestamp,
                "valueQuantity": {
                    "value": float(spo2_val),
                    "unit": "%",
                    "system": "http://unitsofmeasure.org",
                    "code": "%"
                }
            })
            
        # 3. Body Temperature
        if "bodyTemperature" in vitals or "temp" in vitals:
            temp_val = vitals.get("bodyTemperature") or vitals.get("temp", 36.6)
            observations.append({
                "resourceType": "Observation",
                "id": f"obs-temperature-{uuid.uuid4().hex[:12]}",
                "status": "final",
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "vital-signs",
                                "display": "Vital Signs"
                            }
                        ]
                    }
                ],
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8310-5",
                            "display": "Body temperature"
                        }
                    ],
                    "text": "Body temperature"
                },
                "subject": {
                    "reference": "Patient/hk07-patient",
                    "display": "HK-07 Patient"
                },
                "effectiveDateTime": timestamp,
                "valueQuantity": {
                    "value": float(temp_val),
                    "unit": "C",
                    "system": "http://unitsofmeasure.org",
                    "code": "Cel"
                }
            })
            
        # 4. Blood Pressure (systolic & diastolic)
        has_systolic = "systolic" in vitals
        has_diastolic = "diastolic" in vitals
        if has_systolic or has_diastolic:
            sys_val = vitals.get("systolic", 120.0)
            dia_val = vitals.get("diastolic", 80.0)
            observations.append({
                "resourceType": "Observation",
                "id": f"obs-bloodpressure-{uuid.uuid4().hex[:12]}",
                "status": "final",
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "vital-signs",
                                "display": "Vital Signs"
                            }
                        ]
                    }
                ],
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "85354-9",
                            "display": "Blood pressure panel with all children"
                        }
                    ],
                    "text": "Blood pressure systolic & diastolic"
                },
                "subject": {
                    "reference": "Patient/hk07-patient",
                    "display": "HK-07 Patient"
                },
                "effectiveDateTime": timestamp,
                "component": [
                    {
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "8480-6",
                                    "display": "Systolic blood pressure"
                                }
                            ]
                        },
                        "valueQuantity": {
                            "value": float(sys_val),
                            "unit": "mmHg",
                            "system": "http://unitsofmeasure.org",
                            "code": "mm[Hg]"
                        }
                    },
                    {
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "8462-4",
                                    "display": "Diastolic blood pressure"
                                }
                            ]
                        },
                        "valueQuantity": {
                            "value": float(dia_val),
                            "unit": "mmHg",
                            "system": "http://unitsofmeasure.org",
                            "code": "mm[Hg]"
                        }
                    }
                ]
            })
            
        return observations

    @staticmethod
    def to_fhir_condition(entry: ClinicalEntry) -> Dict[str, Any]:
        """
        Translates a ClinicalEntry diagnosis and alert details into an HL7 FHIR Condition resource
        coded using standard SNOMED-CT clinical diagnostic codes.
        """
        timestamp = entry.timestamp or (datetime.utcnow().isoformat() + "Z")
        diagnosis_text = entry.diagnosis or "Clinical evaluation pending"
        diag_lower = diagnosis_text.lower()
        
        # SNOMED-CT Mapping Logic
        snomed_code = "404684003"
        snomed_display = "Clinical finding"
        
        if "stroke" in diag_lower or entry.alert_level == "STROKE":
            snomed_code = "230690003"
            snomed_display = "Cerebrovascular accident"
        elif "tachycardia" in diag_lower or "heart rate" in diag_lower or "hr" in diag_lower:
            snomed_code = "3424008"
            snomed_display = "Tachycardia"
        elif "fever" in diag_lower or "pyrexia" in diag_lower or "high temp" in diag_lower or "sốt" in diag_lower:
            snomed_code = "386661006"
            snomed_display = "Fever"
        elif "hypertension" in diag_lower or "bp" in diag_lower or "pressure" in diag_lower:
            snomed_code = "38341003"
            snomed_display = "Hypertensive disorder"
            
        condition = {
            "resourceType": "Condition",
            "id": f"cond-diagnosis-{uuid.uuid4().hex[:12]}",
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                        "display": "Active"
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed",
                        "display": "Confirmed"
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                            "code": "encounter-diagnosis",
                            "display": "Encounter Diagnosis"
                        }
                    ]
                }
            ],
            "severity": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "6736007" if entry.alert_level in ("CRITICAL", "STROKE") else "255604002",
                        "display": "High" if entry.alert_level in ("CRITICAL", "STROKE") else "Mild"
                    }
                ]
            },
            "code": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": snomed_code,
                        "display": snomed_display
                    }
                ],
                "text": diagnosis_text
            },
            "subject": {
                "reference": "Patient/hk07-patient",
                "display": "HK-07 Patient"
            },
            "onsetDateTime": timestamp,
            "recordedDate": timestamp,
            "note": [
                {
                    "text": f"Alert level: {entry.alert_level}. Actions recommended: {entry.action_recommended or 'None'}. Clinical confidence: {entry.confidence_score}"
                }
            ]
        }
        
        return condition

    @classmethod
    def to_fhir_bundle(cls, entry: ClinicalEntry) -> Dict[str, Any]:
        """
        Combines translated Observation and Condition resources into a standard FHIR Searchset Bundle.
        """
        observations = cls.to_fhir_observations(entry)
        condition = cls.to_fhir_condition(entry)
        
        entry_list = []
        # Append Condition entry
        entry_list.append({
            "fullUrl": f"urn:uuid:{uuid.uuid4()}",
            "resource": condition
        })
        
        # Append Observation entries
        for obs in observations:
            entry_list.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": obs
            })
            
        bundle = {
            "resourceType": "Bundle",
            "id": f"bundle-{uuid.uuid4().hex[:12]}",
            "type": "searchset",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total": len(entry_list),
            "entry": entry_list
        }
        
        return bundle
