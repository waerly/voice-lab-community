"""Memory guard and process cleanup without loading PyTorch or any TTS model."""
import signal
import subprocess
import unittest
from unittest.mock import Mock, patch

import index_resources as resources


class IndexResourceTests(unittest.TestCase):
    def test_preflight_and_input_limits(self):
        with patch.object(resources, 'memory_snapshot', return_value=dict(total=32*resources.GIB, free_percent=48)):
            self.assertEqual(resources.ensure_index_ready('你好')['free_percent'], 48)
            with self.assertRaises(ValueError):
                resources.ensure_index_ready('好' * 201)
        for total, free in [(32, 30), (16, 50)]:
            with patch.object(resources, 'memory_snapshot', return_value=dict(total=total*resources.GIB, free_percent=free)):
                with self.assertRaises(resources.IndexResourceError):
                    resources.ensure_index_ready('你好')
        with patch.object(resources, 'memory_snapshot', side_effect=OSError('unavailable')):
            with self.assertRaises(resources.IndexResourceError):
                resources.ensure_index_ready()

    def test_running_pressure_and_rss_stop_wait(self):
        for free, rss in [(15, 2*resources.GIB), (48, 15*resources.GIB)]:
            process = Mock(pid=123)
            process.wait.side_effect = subprocess.TimeoutExpired('worker', 2)
            with patch.object(resources, 'memory_snapshot', return_value=dict(total=32*resources.GIB, free_percent=free)), \
                 patch.object(resources, 'process_rss', return_value=rss):
                with self.assertRaises(resources.IndexResourceError):
                    resources.wait_for_index(process, lambda: False)

    def test_healthy_worker_finishes_and_cancel_reaps(self):
        process = Mock(pid=123)
        process.wait.side_effect = [subprocess.TimeoutExpired('worker', 2), 0]
        with patch.object(resources, 'memory_snapshot', return_value=dict(total=32*resources.GIB, free_percent=48)), \
             patch.object(resources, 'process_rss', return_value=8*resources.GIB):
            self.assertEqual(resources.wait_for_index(process, lambda: False), 0)
        process.wait.side_effect = subprocess.TimeoutExpired('worker', 2)
        with patch.object(resources, 'stop_process') as stop:
            resources.wait_for_index(process, lambda: True)
            stop.assert_called_once_with(process)

    def test_timeout_and_failed_monitor_are_bounded(self):
        process = Mock(pid=123)
        process.wait.side_effect = subprocess.TimeoutExpired('worker', 2)
        with self.assertRaises(resources.IndexResourceError):
            resources.wait_for_index(process, lambda: False, timeout=0)
        with patch.object(resources, 'memory_snapshot', side_effect=OSError('unavailable')):
            with self.assertRaises(resources.IndexResourceError):
                resources.wait_for_index(process, lambda: False)

    def test_stubborn_worker_is_killed_and_reaped(self):
        process = Mock(pid=123)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('worker', 3), -9]
        with patch.object(resources.os, 'killpg') as kill:
            resources.stop_process(process)
            self.assertEqual(kill.call_args_list[0].args, (123, signal.SIGTERM))
            self.assertEqual(kill.call_args_list[1].args, (123, signal.SIGKILL))
            self.assertEqual(process.wait.call_count, 2)


if __name__ == '__main__':
    unittest.main()
