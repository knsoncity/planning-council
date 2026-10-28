import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

installer=load('installer',ROOT/'distribution/install.py')
launcher=load('launcher',ROOT/'distribution/launcher.py')
builder=load('builder',ROOT/'scripts/build_macos.py')

class DistributionTests(unittest.TestCase):
    def test_archive_is_allowlisted_and_install_update_preserves_extra_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            with patch.object(builder,'OUT',tmp/'output'):
                archive=builder.build()
            with zipfile.ZipFile(archive) as z:
                names=z.namelist()
                self.assertFalse(any('/data/' in n or '/validation/' in n or '.sqlite' in n for n in names))
                self.assertFalse(any('auth.json' in n or '.env' in n for n in names))
                z.extractall(tmp/'unpacked')
            src=tmp/'unpacked/AI-Meeting-Room-macOS'
            skill=(src/'skills/planning-council/SKILL.md').read_text()
            self.assertNotIn('## 선택 역할: AAP 플랫폼 개발 리더',skill)
            self.assertIn('쉬운 토론',skill)
            self.assertNotIn(str(Path.home()), ''.join(p.read_text() for p in src.rglob('*') if p.is_file()))
            import hashlib
            for file,digest in json.loads((src/'MANIFEST.json').read_text()).items():
                self.assertEqual(hashlib.sha256((src/file).read_bytes()).hexdigest(),digest)
            target=tmp/'installed'
            installer.install(src,target)
            (target/'preserve.txt').write_text('existing')
            installer.install(src,target)
            self.assertEqual((target/'preserve.txt').read_text(),'existing')
            (tmp/'unrelated').mkdir()
            with self.assertRaises(ValueError):installer.install(src,tmp/'unrelated')

    def test_environment_does_not_reuse_account_or_override_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'old','CLAUDE_CODE_OAUTH_TOKEN':'old','ANTHROPIC_BASE_URL':'https://untrusted.invalid'}):
                env=launcher.environment(Path(tmp),'test-openai','test-claude')
            self.assertEqual(env['OPENAI_API_KEY'],'test-openai')
            self.assertEqual(env['ANTHROPIC_API_KEY'],'test-claude')
            self.assertNotIn('CLAUDE_CODE_OAUTH_TOKEN',env)
            self.assertNotIn('ANTHROPIC_BASE_URL',env)
            self.assertEqual(Path(env['CODEX_HOME']).parent,Path(tmp))
            self.assertTrue(Path(env['COUNCIL_SKILL_PATH']).is_absolute())

if __name__=='__main__': unittest.main()
