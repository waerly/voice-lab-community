import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
import server


class CommunityTests(unittest.TestCase):
    def test_three_engines_empty_private_data_and_removed_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            for folder in ('jobs','audio','references'):
                (data/folder).mkdir()
            http = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            thread = threading.Thread(target=http.serve_forever,daemon=True)
            states = {name:dict(installed=False,name=name) for name in ('qwen','index','spark')}
            with patch.object(server,'DATA',data), patch.object(server,'PORT',http.server_port), patch.object(server,'readiness',return_value=states):
                thread.start()
                try:
                    base=f'http://127.0.0.1:{http.server_port}'
                    with urllib.request.urlopen(base+'/api/state',timeout=3) as response:
                        result=json.load(response)
                    self.assertEqual(set(result['engines']),{'qwen','index','spark'})
                    self.assertEqual(result['references'],[])
                    self.assertEqual(result['jobs'],[])
                    with urllib.request.urlopen(base+'/api/jobs',timeout=3) as response:
                        self.assertEqual(json.load(response)['total'],0)
                    for route in ['/kokoro','/works','/themes.css','/themes.js','/assets/landscape.png','/../voice-lab/server.py']:
                        with self.assertRaises(urllib.error.HTTPError) as caught:
                            urllib.request.urlopen(base+route,timeout=3)
                        self.assertEqual(caught.exception.code,404)
                finally:
                    http.shutdown();http.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
