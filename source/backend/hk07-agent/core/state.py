import os
import logging
from engine.memory.lance_memory import LanceMemory
from services.knowledge_ingestion import KnowledgeIngestionService
from engine.arbitrator.arbitrator import Arbitrator
from engine.agents.agent_orchestrator import AgentOrchestrator
from engine.agents.perception_agent import PerceptionAgent
from engine.agents.hardware_command_agent import HardwareCommandAgent

log = logging.getLogger("hk07.state")

memory = LanceMemory()
ingestion_service = KnowledgeIngestionService(memory)
arbitrator = Arbitrator()
orchestrator = AgentOrchestrator(memory=memory, arbitrator=arbitrator)

USE_ORCHESTRATOR_V2 = os.getenv("USE_ORCHESTRATOR_V2", "true").lower() == "true"
if USE_ORCHESTRATOR_V2:
    from engine.agents.agent_orchestrator_v2 import AgentOrchestratorV2
    orchestrator_v2 = AgentOrchestratorV2(memory=memory, arbitrator=arbitrator)
else:
    orchestrator_v2 = None

perception_agent = PerceptionAgent(arbitrator=arbitrator)
hardware_command_agent = HardwareCommandAgent(arbitrator=arbitrator)

from services.camera_stream import CameraStreamWorker, get_camera_url
from utils.vision_pipeline import VisionPipeline

camera_worker = CameraStreamWorker(get_camera_url)
camera_url = get_camera_url()
vision_pipeline = VisionPipeline(camera_url) if camera_url else None

