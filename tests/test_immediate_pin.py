import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

import corectl as core


class ImmediatePinTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.state = root / '.ham-xray' / 'fixture'
        self.state.mkdir(parents=True)
        base = root / 'docker-compose.yml'
        base.write_text('fixture')
        shutil.copy2(core.__file__, self.state / 'operation.py')
        (self.state / 'manifest.json').write_text(json.dumps({
            'prepared_at': time.time(), 'compose_sha': core.sha(base),
            'override_before': None, 'image': 'fixture', 'godebug': '',
        }))
        for name, ctx in (
            ('root', patch.object(core, 'ROOT', root)),
            ('run', patch.object(core, 'run', return_value=b'')),
            ('accept', patch.object(core, 'accept')),
            ('rollback', patch.object(core, 'rollback')),
            ('sleep', patch.object(core.time, 'sleep')),
        ):
            setattr(self, name, ctx.start())
            self.addCleanup(ctx.stop)

    def test_wait_for_start_then_pin_without_timer(self):
        self.accept.side_effect = [core.NoRunningCore(), None]
        core.apply(self.state)
        self.assertEqual(self.accept.call_count, 2)
        self.rollback.assert_not_called()
        self.assertFalse(any(c.args[0][0] == 'systemd-run' for c in self.run.call_args_list))
        self.assertEqual(json.loads((self.state / 'manifest.json').read_text())['pin_mode'], 'immediate')

    def test_rejected_pin_attempts_immediate_rollback(self):
        self.accept.side_effect = ValueError('mismatch')
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            core.apply(self.state)
        self.rollback.assert_called_once_with(self.state)
