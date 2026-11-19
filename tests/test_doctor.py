import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import corectl as core
import doctor


class DoctorTests(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        root=Path(tmp.name).resolve()
        self.state=root/'.ham-xray'/'fixture'
        self.state.mkdir(parents=True)
        self.binary=self.state/'xray';self.binary.write_bytes(b'fixture')
        self.base=root/'docker-compose.yml';self.base.write_text('initial')
        self.override=root/'docker-compose.override.yml'
        self.override.write_text(json.dumps({core.MARKER:True,'services':{'remnanode':{
            'image':'img','environment':{'GODEBUG':'multipathtcp=0'},
            'volumes':[{'source':str(self.binary),'target':'/usr/local/bin/xray'}]}}}))
        manifest={'version':'26.7.28','image':'img','unit':'ham-xray-return-fixture',
                  'override_sha':core.sha(self.override),'compose_sha':core.sha(self.base),'binary_sha':core.sha(self.binary)}
        (self.state/'manifest.json').write_text(json.dumps(manifest))
        self.container={'Image':'img','State':{'Running':True},'Mounts':[{'Type':'bind',
            'Destination':'/usr/local/bin/xray','Source':str(self.binary),'RW':False}]}
        self.top=b'PID COMMAND\n123 xray\n';self.timer='inactive'
        real_sha=core.sha
        for ctx in (patch.object(core,'ROOT',root),
                    patch.object(core,'run',side_effect=lambda a:json.dumps([self.container]).encode() if a[1]=='inspect' else self.top),
                    patch.object(core,'sha',side_effect=lambda p:real_sha(self.binary if p==Path('/proc/123/exe') else p)),
                    patch.object(doctor.subprocess,'run',side_effect=lambda *a,**kw:SimpleNamespace(returncode=0,stdout=self.timer))):
            ctx.start();self.addCleanup(ctx.stop)

    def test_matches_or_pending(self):
        self.assertEqual(doctor.inspect_pin()[1],'matched')
        self.timer='active';self.assertEqual(doctor.inspect_pin()[1],'temporary')

    def test_base_only_recreation(self):
        self.container['Mounts']=[];self.assertEqual(doctor.inspect_pin()[1],'drift')

    def test_changed_binary(self):
        self.binary.write_bytes(b'other');self.assertEqual(doctor.inspect_pin()[1],'drift')

    def test_no_running_core(self):
        self.top=b'PID COMMAND\n';self.assertEqual(doctor.inspect_pin()[1],'unverified')

    def test_missing_override(self):
        self.override.unlink();self.assertEqual(doctor.inspect_pin()[1],'unmanaged')

    def test_unknown_timer(self):
        self.timer='failed';self.assertEqual(doctor.inspect_pin()[1],'unknown')

    def test_fresh_config_read_failure_is_not_a_blank_config(self):
        with patch.object(core,'runtime',side_effect=RuntimeError('cannot read live configuration')), patch.object(core,'run',return_value=b'Xray 26.7.28 test'):
            with self.assertRaisesRegex(RuntimeError,'cannot read'):
                core.check_core(self.state,'img','26.7.28',fresh=True)
