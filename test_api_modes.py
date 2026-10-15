"""HTTP validation without loading any model or touching saved user data."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
import server


class ModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name)
        for folder in ('jobs','audio','references'):
            (cls.data/folder).mkdir()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1',0), server.Handler)
        cls.port = cls.http.server_port
        cls.patches = [patch.object(server,'DATA',cls.data), patch.object(server,'PORT',cls.port),
            patch.object(server,'readiness',return_value={
                'qwen':dict(installed=True,custom_ready=True,design_ready=True,name='Qwen'),
                'spark':dict(installed=True,name='Spark'),'index':dict(installed=True,name='Index')}),
            patch.object(server,'run',side_effect=lambda jobs: server.RUN_LOCK.release())]
        cls.patches.append(patch.object(server, 'ensure_index_ready'))
        for p in cls.patches:p.start()
        cls.thread = threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=2)
        for p in cls.patches:p.stop()
        cls.tmp.cleanup()

    def request(self, **values):
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}/api/generate',
            data=json.dumps(values).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)

    def test_qwen_design_requires_description(self):
        self.assertEqual(self.request(engines=['qwen'],mode='design',text='你好')[0],400)
        status,body=self.request(engines=['qwen'],mode='design',text='你好',instruction='温柔女声')
        self.assertEqual(status,202)
        self.assertEqual(body['jobs'][0]['mode'],'design')
        self.assertIsNone(body['jobs'][0]['reference'])

    def test_design_snapshot_does_not_use_selected_reference(self):
        status, body = self.request(engines=['qwen'], mode='design', text='你好',
            instruction='温暖自然的女声', reference_id='not-used-in-design',
            voice_design_template='温暖女旁白', voice_design_modified=True)
        self.assertEqual(status, 202)
        job = body['jobs'][0]
        self.assertEqual(job['model_variant'], 'VoiceDesign')
        self.assertIsNone(job['reference'])
        self.assertEqual(job['voice_design_template'], '温暖女旁白')
        saved = json.loads((self.data/'jobs'/(job['id']+'.json')).read_text())
        self.assertEqual(saved['instruction'], '温暖自然的女声')
        self.assertTrue(saved['voice_design_modified'])

    def test_spark_creation_and_invalid_modes(self):
        status,body=self.request(engines=['spark'],mode='design',text='你好',gender='female')
        self.assertEqual(status,202)
        self.assertEqual(body['jobs'][0]['gender'],'female')
        self.assertEqual(self.request(engines=['spark'],mode='custom',text='你好')[0],400)
        self.assertEqual(self.request(engines=['index'],mode='design',text='你好')[0],400)

    def test_reference_and_length_validation(self):
        self.assertEqual(self.request(engines=['spark'],mode='clone',text='你好')[0],400)
        self.assertEqual(self.request(engines=['qwen'],mode='design',text='好'*121,instruction='女声')[0],400)

    def test_index_memory_protection_rejects_without_starting_job(self):
        identity = 'a' * 32
        (self.data/'references'/(identity+'.json')).write_text(json.dumps(
            dict(id=identity, name='测试', path='unused.wav', transcript='你好')))
        with patch.object(server, 'ensure_index_ready', side_effect=server.IndexResourceError('内存余量不足')):
            before = len(list((self.data/'jobs').glob('*.json')))
            status, body = self.request(engines=['qwen','index'], text='你好', reference_id=identity)
            self.assertEqual(status, 409)
            self.assertIn('内存余量不足', body['error'])
            self.assertEqual(len(list((self.data/'jobs').glob('*.json'))), before)
            self.assertFalse(server.RUN_LOCK.locked())


if __name__=='__main__':unittest.main()
