"""Model bootstrap checks without network access or AI dependencies."""
import io
import json
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


SCRIPT = Path(__file__).with_name("prepare_speaches.py")
MODEL = "Systran/faster-distil-whisper-small.en"


class BootstrapTest(unittest.TestCase):
    def run_bootstrap(self, models, download=None):
        responses = [io.BytesIO(json.dumps({"data": models}).encode())]
        if download is not None:
            responses.append(download)
        with patch("urllib.request.urlopen", side_effect=responses) as request:
            runpy.run_path(str(SCRIPT))
        return request

    def test_cached_model_needs_no_download(self):
        request = self.run_bootstrap([{"id": MODEL}])
        self.assertEqual(request.call_count, 1)

    def test_missing_model_is_downloaded(self):
        request = self.run_bootstrap([], io.BytesIO(b"{}"))
        self.assertEqual(request.call_count, 2)
        download = request.call_args.args[0]
        self.assertEqual(download.get_method(), "POST")
        self.assertEqual(download.full_url, f"http://speaches:8000/v1/models/{MODEL}")

    def test_download_failure_prevents_success(self):
        with self.assertRaises(HTTPError):
            self.run_bootstrap([], HTTPError("http://speaches", 503, "Unavailable", {}, None))


if __name__ == "__main__":
    unittest.main()
