"""Opt-in Linux integration test on a disposable Docker daemon, no registry."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import uuid
from unittest.mock import patch

import corectl as core


@unittest.skipUnless(os.getenv('HAM_TEST_STATIC_BUSYBOX'),'requires disposable Docker and static busybox')
class RecreateTest(unittest.TestCase):
    def test_updater_uses_only_main_file(self):
        tag='ham-pin-fixture:'+uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory(prefix='ham-pin-') as tmp:
            root=Path(tmp);state=root/'.ham-xray'/'fixture';state.mkdir(parents=True)
            buf=io.BytesIO()
            with tarfile.open(fileobj=buf,mode='w') as tar:
                tar.add(os.environ['HAM_TEST_STATIC_BUSYBOX'],arcname='bin/busybox',recursive=False)
            subprocess.run(['docker','import','-',tag],input=buf.getvalue(),check=True,stdout=subprocess.DEVNULL)
            self.addCleanup(subprocess.run,['docker','image','rm',tag],check=True)
            base=root/'docker-compose.yml';override=root/'docker-compose.override.yml'
            base.write_text(json.dumps({'services':{'remnanode':{'image':tag,'network_mode':'none',
                                          'command':['/bin/busybox','sleep','600']}}}))
            shutil.copy2(base,state/'compose.before.yml');shutil.copy2(core.__file__,state/'operation.py')
            (state/'xray').write_bytes(b'confirmed fixture 26.7.28')
            binding={'type':'bind','source':str(state/'xray'),'target':'/usr/local/bin/xray','read_only':True}
            override.write_text(json.dumps({core.MARKER:True,'services':{'remnanode':{'image':tag,
                                            'volumes':[binding],'environment':{'GODEBUG':'multipathtcp=0'}}}}))
            m={'compose_sha':core.sha(base),'override_sha':core.sha(override),'binary_sha':core.sha(state/'xray')}
            def compose(files,*args):
                return subprocess.check_output(['docker','compose',*[v for f in files for v in ['-f',str(f)]],*args],cwd=root)
            try:
                compose([base,override],'up','-d','--pull','never')
                before=compose([base],'ps','-q','remnanode').strip()
                with patch.object(core,'ROOT',root),patch.object(core,'run',side_effect=lambda a:subprocess.check_output(a,cwd=root)):
                    core.persist_core(state,m)
                compose([base],'up','-d','--force-recreate','--pull','never')
                after=compose([base],'ps','-q','remnanode').strip()
                self.assertTrue(before and after and before!=after)
                self.assertEqual(compose([base],'exec','-T','remnanode','/bin/busybox','cat','/usr/local/bin/xray'),
                                 (state/'xray').read_bytes())
            finally:
                compose([base],'down','--timeout','1')
