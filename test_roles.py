import json
from pathlib import Path
import tempfile
import unittest
import wave
from role_library import save_role


def save(path, obj):
    path.write_text(json.dumps(obj))


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        for folder in ('jobs', 'audio', 'references'):
            (self.data/folder).mkdir()
        self.identity = 'a'*32
        self.job = dict(status='done', text='你好，欢迎来听故事。', model='test', mode='design', instruction='温暖女声', spark_pitch=.5, spark_speed=1.5, spark_seed=123)
        save(self.data/'jobs'/(self.identity+'.json'), self.job)
        self.audio = self.data/'audio'/(self.identity+'.wav')
        self.make_audio(4)

    def make_audio(self, duration):
        with wave.open(str(self.audio), 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\x00\x00'*int(24000*duration))

    def test_independent_sample_and_provenance(self):
        role = save_role(self.data, self.identity, '温暖讲述', save)
        self.audio.unlink()
        self.assertTrue(Path(role['path']).is_file())
        self.assertEqual(role['transcript'], self.job['text'])
        self.assertEqual(role['source_parameters']['instruction'], '温暖女声')
        self.assertTrue(role['synthetic'])
        self.assertEqual(role['source_parameters']['spark_seed'], 123)
        self.assertEqual(role['source_parameters']['spark_pitch'], .5)
        self.assertEqual(role['source_parameters']['spark_speed'], 1.5)
        self.assertEqual(json.loads(Path(role['path']).with_suffix('.json').read_text()), role)

    def test_duration_boundary_never_truncates(self):
        for duration in (2, 31):
            self.make_audio(duration)
            with self.assertRaises(ValueError):
                save_role(self.data, self.identity, '角色', save)
        self.assertEqual(list((self.data/'references').iterdir()), [])

    def test_reject_unfinished_and_empty_name(self):
        with self.assertRaises(ValueError):
            save_role(self.data, self.identity, ' ', save)
        self.job['status'] = 'running'
        save(self.data/'jobs'/(self.identity+'.json'), self.job)
        with self.assertRaises(ValueError):
            save_role(self.data, self.identity, '角色', save)


if __name__ == '__main__':
    unittest.main()
