"""
test_local_slm_offline.py — Unit & Integration Test Suite for Local SLM Fallback Engine

Verifies both the zero-dependency rule-based fallback matrix and the local SLM inference path.
"""

import sys
from unittest.mock import MagicMock, patch

# Mock llama_cpp module in sys.modules to prevent ModuleNotFoundError when not installed
sys.modules['llama_cpp'] = MagicMock()

import os
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm_client import LocalOfflineFallback


class TestLocalOfflineFallback(unittest.TestCase):
    
    def setUp(self):
        # Reset the cached local SLM model instance to ensure no test cross-contamination
        LocalOfflineFallback._model_instance = None
        
    def tearDown(self):
        # Clean up cached instance after each test run
        LocalOfflineFallback._model_instance = None
    
    # ── Rule-Based Path Tests ──────────────────────────────────────────────────
    
    def test_rule_based_completion_greetings(self):
        """Verify greeting query matches rule-based response."""
        res = LocalOfflineFallback.get_completion_fallback("Xin chào, bạn khỏe không?")
        self.assertIn("Baymax", res)
        self.assertIn("offline", res.lower())

    def test_rule_based_completion_emergency(self):
        """Verify emergency query triggers rule-based emergency message."""
        res = LocalOfflineFallback.get_completion_fallback("Cấp cứu! Tôi đang bị đột quỵ")
        self.assertIn("EMERGENCY", res)
        self.assertIn("local emergency protocol", res.lower())

    def test_rule_based_completion_symptoms(self):
        """Verify symptoms query advise vitals check."""
        res = LocalOfflineFallback.get_completion_fallback("Tôi bị đau ngực dữ dội")
        self.assertIn("offline", res.lower())
        self.assertIn("vitals", res.lower())

    def test_rule_based_completion_status(self):
        """Verify status query returns offline status message."""
        res = LocalOfflineFallback.get_completion_fallback("Kiểm tra trạng thái kết nối")
        self.assertIn("ONLINE", res)
        self.assertIn("unreachable", res.lower())

    def test_rule_based_tool_call_emergency(self):
        """Verify emergency query maps to trigger_sos_protocol tool."""
        res = LocalOfflineFallback.get_tool_call_fallback("Tôi bị tai nạn đột quỵ nguy kịch", [])
        self.assertIn("trigger_sos_protocol", res["tools_to_invoke"])
        self.assertEqual(res["tool_calls"][0]["tool_name"], "trigger_sos_protocol")

    def test_rule_based_tool_call_symptoms(self):
        """Verify clinical symptoms query maps to analyze_clinical_symptoms tool."""
        res = LocalOfflineFallback.get_tool_call_fallback("Tôi bị đau đầu và sốt cao", [])
        self.assertIn("analyze_clinical_symptoms", res["tools_to_invoke"])
        self.assertEqual(res["tool_calls"][0]["tool_name"], "analyze_clinical_symptoms")

    def test_rule_based_tool_call_status(self):
        """Verify hardware/status checks map to execute_system_query tool."""
        res = LocalOfflineFallback.get_tool_call_fallback("Kiểm tra trạng thái Lidar", [])
        self.assertIn("execute_system_query", res["tools_to_invoke"])
        self.assertEqual(res["tool_calls"][0]["tool_name"], "execute_system_query")
        self.assertEqual(res["tool_calls"][0]["parameters"]["device"], "lidar")

    def test_rule_based_tool_call_guidelines(self):
        """Verify medical guideline query maps to search_medical_guidelines tool."""
        res = LocalOfflineFallback.get_tool_call_fallback("Hướng dẫn điều trị đột quỵ FAST", [])
        self.assertIn("search_medical_guidelines", res["tools_to_invoke"])

    # ── Local SLM Mock Integration Tests ─────────────────────────────────────
    
    @patch("services.llm_client.LLAMA_CPP_AVAILABLE", True)
    @patch("os.path.exists")
    @patch("llama_cpp.Llama")
    def test_local_slm_text_completion_path(self, mock_llama_class, mock_exists):
        """Verify GGUF model loading and text completion generation path when Llama is active."""
        # 1. Mock path checks and llama model
        mock_exists.return_value = True
        
        mock_model = MagicMock()
        mock_model.return_value = {
            "choices": [{"text": "Hello from mock Phi-3 SLM!"}]
        }
        mock_llama_class.return_value = mock_model
        
        # Reset local cache
        LocalOfflineFallback._model_instance = None
        
        # 2. Execute completion
        res = LocalOfflineFallback.get_completion_fallback("Xin chào", system_prompt="Test system")
        
        # 3. Assertions
        mock_llama_class.assert_called_once()
        mock_model.assert_called_once()
        self.assertEqual(res, "Hello from mock Phi-3 SLM!")

    @patch("services.llm_client.LLAMA_CPP_AVAILABLE", True)
    @patch("os.path.exists")
    @patch("llama_cpp.Llama")
    def test_local_slm_tool_call_path(self, mock_llama_class, mock_exists):
        """Verify GGUF model tool calling routing path and JSON parsing."""
        mock_exists.return_value = True
        
        mock_model = MagicMock()
        mock_model.return_value = {
            "choices": [{
                "text": '{"tools_to_invoke": ["analyze_clinical_symptoms"], "tool_calls": [{"tool_name": "analyze_clinical_symptoms", "parameters": {"symptom_description": "shortness of breath", "urgency_level": "HIGH"}}]}'
            }]
        }
        mock_llama_class.return_value = mock_model
        
        LocalOfflineFallback._model_instance = None
        
        # Execute tool call
        res = LocalOfflineFallback.get_tool_call_fallback("I am having chest pain and shortness of breath", [])
        
        # Assertions
        self.assertIn("analyze_clinical_symptoms", res["tools_to_invoke"])
        self.assertEqual(res["tool_calls"][0]["parameters"]["urgency_level"], "HIGH")


if __name__ == "__main__":
    unittest.main()
