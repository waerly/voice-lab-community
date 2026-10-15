"""Exercise real WAV assembly with a tiny fake model; never import PyTorch."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import index_worker
from index_resources import GIB
from worker import text_segments


@unittest.skipUnless(importlib.util.find_spec('soundfile'), 'run in the existing qwen-venv for WAV verification')
class IndexWorkerTests(unittest.TestCase):
    def render(self, fail=False):
        import soundfile as sf
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            reference = directory/'reference.wav'
            sf.write(str(reference), [0.0]*72000, 24000)
            output = directory/'output.wav'
            calls = []

            def infer(**values):
                calls.append(values)
                if fail and len(calls) == 2:
                    raise RuntimeError('simulated allocation failure')
                sf.write(values['output_path'], [0.1]*2205, 22050)

            torch = types.ModuleType('torch')
            torch.set_num_threads = Mock(); torch.set_num_interop_threads = Mock()
            torch.manual_seed = Mock()
            torch.mps = Mock()
            torch.mps.recommended_max_memory.return_value = 24*GIB
            engine = types.ModuleType('indextts.infer_v2_5')
            engine.IndexTTS2 = Mock(return_value=Mock(infer=infer))
            modules = {'torch':torch, 'indextts':types.ModuleType('indextts'),
                       'indextts.infer_v2_5':engine}
            job = dict(text='这是一句用于验证分段合并的测试文案。'*6,
                       output=str(output), reference={'path':str(reference)},
                       emotion='reference', duration_factor=1)
            with patch.dict(sys.modules, modules), \
                 patch.object(index_worker, 'ensure_index_ready', return_value={'total':32*GIB}):
                if fail:
                    with self.assertRaisesRegex(RuntimeError, 'simulated allocation failure'):
                        index_worker.render_index(job, directory, text_segments)
                    self.assertFalse(output.exists())
                else:
                    index_worker.render_index(job, directory, text_segments)
                    self.assertGreater(len(calls), 1)
                    self.assertTrue(all(len(c['text']) <= 40 and c['num_beams'] == 1 for c in calls))
                    self.assertEqual(''.join(c['text'] for c in calls), job['text'])
                    audio = sf.info(str(output))
                    self.assertEqual(audio.frames, len(calls)*2205+(len(calls)-1)*4410)
                    self.assertEqual(audio.samplerate, 22050)
                    self.assertEqual(torch.mps.empty_cache.call_count, len(calls))
                    fraction = torch.mps.set_per_process_memory_fraction.call_args.args[0]
                    self.assertAlmostEqual(fraction, .4)
                self.assertFalse(output.with_suffix('.partial.wav').exists())

    def test_wav_assembly_and_allocator_limit(self):
        self.render()

    def test_failed_segment_never_publishes_partial_audio(self):
        self.render(fail=True)


if __name__ == '__main__':
    unittest.main()
