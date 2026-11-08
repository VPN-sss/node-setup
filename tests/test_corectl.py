import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('corectl',Path(__file__).parents[1]/'corectl.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)

class CorePolicyTests(unittest.TestCase):
    def test_verified_artifact_is_pinned(self):
        version,url,digest=core.artifact('verified','x86_64')
        self.assertEqual(version,'26.7.28');self.assertIn('/v26.7.28/Xray-linux-64.zip',url);self.assertEqual(len(digest),64)

    def test_unsupported_architecture_fails_closed(self):
        with self.assertRaises(ValueError):core.artifact('verified','unknown')

    def test_mptcp_option_preserves_other_debug_settings(self):
        self.assertEqual(core.godebug('netdns=go,multipathtcp=1,gctrace=1'),'netdns=go,gctrace=1,multipathtcp=0')
        self.assertEqual(core.godebug(core.godebug('')),core.godebug(''))

    def test_unowned_override_is_preserved(self):
        for raw in ['services:\n  remnanode: {}',json.dumps({'services':{}})]:
            with self.assertRaises(ValueError):core.managed_override(raw)

    def test_own_override_is_allowed(self):
        core.managed_override(json.dumps({core.MARKER:True,'services':{'remnanode':{'image':'sha256:test','environment':{'GODEBUG':'multipathtcp=0'},'volumes':[{'target':'/usr/local/bin/xray'}]}}}));core.managed_override(None)

    def test_extended_managed_override_is_not_overwritten(self):
        cfg={core.MARKER:True,'services':{'remnanode':{'image':'sha256:test','environment':{'GODEBUG':'multipathtcp=0'},'volumes':[{'target':'/usr/local/bin/xray'}],'mem_limit':'1g'}}}
        with self.assertRaises(ValueError):core.managed_override(json.dumps(cfg))

    def test_state_must_be_within_managed_directory(self):
        with self.assertRaises(ValueError):core.state_path('/tmp')

    def test_checksum_changes_when_binary_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'xray';file.write_bytes(b'one');first=core.sha(file);file.write_bytes(b'two');self.assertNotEqual(first,core.sha(file))

    def test_latest_rejects_unverified_asset(self):
        release={'tag_name':'v26.10.31','assets':[{'name':'Xray-linux-64.zip','digest':'','browser_download_url':'https://example.org/xray.zip'}]}
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps(release).encode()
        with patch.object(core.urllib.request,'urlopen',return_value=Reply()):
            with self.assertRaises(ValueError):core.artifact('latest','x86_64')

    def test_latest_rejects_unexpected_tag(self):
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{"tag_name":"v../bad"}'
        with patch.object(core.urllib.request,'urlopen',return_value=Reply()):
            with self.assertRaises(ValueError):core.artifact('latest','x86_64')

if __name__=='__main__':unittest.main()
