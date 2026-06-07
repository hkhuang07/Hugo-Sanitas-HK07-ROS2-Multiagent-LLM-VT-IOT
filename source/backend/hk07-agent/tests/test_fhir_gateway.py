"""
test_fhir_gateway.py — Unit tests for FhirGatewayService
"""

import sys
import os
import unittest
from datetime import datetime

# Add agent package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.blackboard_service import ClinicalEntry
from services.fhir_gateway_service import FhirGatewayService

class TestFhirGateway(unittest.TestCase):
    def setUp(self):
        self.entry = ClinicalEntry(
            alert_level="CRITICAL",
            vitals={
                "heartRate": 145,
                "spo2": 89.5,
                "bodyTemperature": 38.8,
                "systolic": 175,
                "diastolic": 105,
                "deviceId": "wristband-test-01"
            },
            diagnosis="Tachycardia, high temperature, hypertensive crisis",
            action_recommended="Urgent clinical evaluation recommended",
            confidence_score=0.95
        )

    def test_to_fhir_observations(self):
        obs_list = FhirGatewayService.to_fhir_observations(self.entry)
        self.assertEqual(len(obs_list), 4) # HR, SpO2, Temp, Blood Pressure panel
        
        # Verify Observation 1 (Heart Rate)
        hr_obs = next(o for o in obs_list if o["code"]["coding"][0]["code"] == "8867-4")
        self.assertEqual(hr_obs["resourceType"], "Observation")
        self.assertEqual(hr_obs["valueQuantity"]["value"], 145.0)
        self.assertEqual(hr_obs["valueQuantity"]["code"], "/min")
        self.assertEqual(hr_obs["subject"]["reference"], "Patient/hk07-patient")
        
        # Verify Observation 2 (SpO2)
        spo2_obs = next(o for o in obs_list if o["code"]["coding"][0]["code"] == "2708-6")
        self.assertEqual(spo2_obs["valueQuantity"]["value"], 89.5)
        self.assertEqual(spo2_obs["valueQuantity"]["code"], "%")
        
        # Verify Observation 3 (Temp)
        temp_obs = next(o for o in obs_list if o["code"]["coding"][0]["code"] == "8310-5")
        self.assertEqual(temp_obs["valueQuantity"]["value"], 38.8)
        self.assertEqual(temp_obs["valueQuantity"]["code"], "Cel")

        # Verify Observation 4 (Blood Pressure Panel)
        bp_obs = next(o for o in obs_list if o["code"]["coding"][0]["code"] == "85354-9")
        self.assertEqual(len(bp_obs["component"]), 2)
        sys_comp = next(c for c in bp_obs["component"] if c["code"]["coding"][0]["code"] == "8480-6")
        dia_comp = next(c for c in bp_obs["component"] if c["code"]["coding"][0]["code"] == "8462-4")
        self.assertEqual(sys_comp["valueQuantity"]["value"], 175.0)
        self.assertEqual(dia_comp["valueQuantity"]["value"], 105.0)

    def test_to_fhir_condition(self):
        cond = FhirGatewayService.to_fhir_condition(self.entry)
        self.assertEqual(cond["resourceType"], "Condition")
        self.assertEqual(cond["clinicalStatus"]["coding"][0]["code"], "active")
        self.assertEqual(cond["verificationStatus"]["coding"][0]["code"], "confirmed")
        self.assertEqual(cond["severity"]["coding"][0]["display"], "High")
        
        # Coded diagnosis check
        self.assertEqual(cond["code"]["coding"][0]["code"], "3424008") # Tachycardia SNOMED code
        self.assertEqual(cond["code"]["coding"][0]["display"], "Tachycardia")
        self.assertIn("crisis", cond["code"]["text"])

    def test_to_fhir_bundle(self):
        bundle = FhirGatewayService.to_fhir_bundle(self.entry)
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "searchset")
        self.assertEqual(bundle["total"], 5) # 1 Condition + 4 Observations
        self.assertEqual(len(bundle["entry"]), 5)

if __name__ == "__main__":
    unittest.main()
