import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import corectl as core


class BasePinTests(unittest.TestCase):
    def test_preserves_foreign_extends(self):
        for raw in ('services:\n  remnanode:\n    extends: other\n',
                    '{"services":{"remnanode":{"extends":"other"}}}'):
            with self.assertRaises(ValueError):core.with_core_extension(raw,Path('/test'))

    def test_repeat_replaces_owned_extension(self):
        for raw in ('services:\n  remnanode:\n    image: example\n','{"services":{"remnanode":{}}}'):
            first=core.with_core_extension(raw,Path('/test/first'))
            second=core.with_core_extension(first,Path('/test/second'))
            self.assertNotIn('first',second);self.assertEqual(second.count('extends'),1)

    @unittest.skipUnless(os.getenv('HAM_TEST_COMPOSE_BIN'),'requires Docker Compose CLI')
    def test_real_compose_models_and_rollback(self):
        for base_json in (True,False):
            with self.subTest(base_json=base_json),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);state=root/'.ham-xray'/'transaction';state.mkdir(parents=True)
                base=root/'docker-compose.yml';override=root/'docker-compose.override.yml'
                svc={'image':'example:latest','environment':['SECRET_KEY=${EXAMPLE:-fixture}'],'volumes':['./cert:/cert:ro']}
                raw=json.dumps({'services':{'remnanode':svc}}) if base_json else (
                    'services:\n  remnanode:\n    image: example:latest\n    environment:\n'
                    '      - SECRET_KEY=${EXAMPLE:-fixture}\n    volumes:\n      - ./cert:/cert:ro\n')
                base.write_text(raw);(state/'xray').write_bytes(b'fixture');shutil.copy2(base,state/'compose.before.yml')
                shutil.copy2(core.__file__,state/'operation.py')
                binding={'type':'bind','source':str(state/'xray'),'target':'/usr/local/bin/xray','read_only':True}
                override.write_text(json.dumps({core.MARKER:True,'services':{'remnanode':{'image':'example:pinned',
                                    'environment':{'GODEBUG':'multipathtcp=0'},'volumes':[binding]}}}))
                m={'version':'26.7.28','compose_sha':core.sha(base),'binary_sha':core.sha(state/'xray'),
                   'override_sha':core.sha(override),'image_ref':'example:latest','image':'img','override_before':None,'unit':'test'}
                def render(args,**kwargs):
                    self.assertEqual(args[:2],['docker','compose'])
                    return subprocess.check_output([os.environ['HAM_TEST_COMPOSE_BIN'],*args[2:]],cwd=root)
                with patch.object(core,'ROOT',root),patch.object(core,'run',side_effect=render):
                    core.persist_core(state,m)
                    standalone=json.loads(render(['docker','compose','-f',str(base),'config','--format','json']))
                    volumes=standalone['services']['remnanode']['volumes']
                    self.assertTrue(any(v['target']==binding['target'] and v['source']==binding['source'] and v['read_only'] for v in volumes))
                    self.assertIn('${EXAMPLE:-fixture}',base.read_text())
                with patch.object(core,'ROOT',root),patch.object(core,'run',return_value=b'[{"Id":"img"}]'),patch.object(core.subprocess,'run'):
                    core.rollback(state)
                self.assertEqual(base.read_text(),raw);self.assertFalse(override.exists())
