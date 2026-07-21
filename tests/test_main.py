"""
test_main.py

Quick integration tests for the FastAPI endpoints exposed by
`Backend.main`. Ensures the `/verify` endpoint preserves the expected
response shape (adds a top-level `status` field) even when the pipeline
returns a pre-crafted payload.
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from Backend import main


class VerifyEndpointTests(unittest.TestCase):
    def test_verify_endpoint_adds_status_field(self):
        client = TestClient(main.app)

        payload = {
            "original_text": "hello",
            "english_translation": "hello",
            "core_claim": "hello",
            "sources": [],
            "verdict": "uncertain",
            "confidence": "low",
            "reasoning": "test reasoning",
            "is_error": False,
        }

        with patch.object(main.pipeline, "verify", return_value=payload):
            response = client.post("/verify", json={"claim": "hello"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
