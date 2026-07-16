from fastapi import APIRouter
from services.fhir_gateway_service import FhirGatewayService
from services.blackboard_service import get_blackboard

router = APIRouter(tags=["fhir"])

@router.get("/api/v1/fhir/observation/latest")
async def fhir_observation_latest():
    """
    Get the latest Blackboard ClinicalEntry formatted as a list of FHIR Observations.
    """
    bb = get_blackboard()
    clinical = await bb.read_latest_clinical()
    if clinical is None:
        return {"status": "no_data", "observations": []}
    
    observations = FhirGatewayService.to_fhir_observations(clinical)
    return {"status": "ok", "observations": observations}

@router.get("/api/v1/fhir/condition/latest")
async def fhir_condition_latest():
    """
    Get the latest Blackboard ClinicalEntry formatted as an HL7 FHIR Condition resource.
    """
    bb = get_blackboard()
    clinical = await bb.read_latest_clinical()
    if clinical is None:
        return {"status": "no_data", "condition": None}
    
    condition = FhirGatewayService.to_fhir_condition(clinical)
    return {"status": "ok", "condition": condition}

@router.get("/api/v1/fhir/clinical-bundle/latest")
async def fhir_clinical_bundle_latest():
    """
    Get the latest clinical status as a combined FHIR searchset transaction bundle.
    """
    bb = get_blackboard()
    clinical = await bb.read_latest_clinical()
    if clinical is None:
        return {"status": "no_data", "bundle": None}
    
    bundle = FhirGatewayService.to_fhir_bundle(clinical)
    return {"status": "ok", "bundle": bundle}

