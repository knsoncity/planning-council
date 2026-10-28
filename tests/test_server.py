import json
import sqlite3
from contextlib import closing
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Store, Engine, Cancelled, parse_result, build_prompt, invoke, make_handler, ROSTER, CBO, member_prompt, public_meeting

def answer():
    return dict(position='보류', summary='제공 근거를 추가로 확인해야 합니다.',
                perspectives=[dict(role=str(i), view='검증 필요') for i in range(5)],
                evidence_ids=['E1'], risks=['자료 미검증'], challenges=[], changes=[],
                next_steps=['실측 확인'], dissent=[])

class CouncilTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.mid = self.store.create('동일 안건', '아이템 유지', '공급 조건 미확인', 'SKILL SNAPSHOT', protocol='teams-v1')

    def tearDown(self):
        self.tmp.cleanup()

    def wait(self, engine):
        until = time.monotonic() + 5
        while engine.active and time.monotonic() < until:
            time.sleep(.01)
        self.assertIsNone(engine.active)

    def test_failure_retry_preserves_completed_and_round_cap(self):
        calls = []
        failed = False
        def runner(provider, prompt, directory, cancel, emit):
            nonlocal failed
            calls.append(provider)
            if len(calls) == 2 and not failed:
                failed = True
                raise RuntimeError('simulated provider failure')
            return json.dumps(answer()), None
        engine = Engine(self.store, runner)
        engine.start(self.mid); self.wait(engine)
        before = self.store.get(self.mid)
        first_id = before['runs'][0]['id']
        self.assertEqual(before['status'], 'failed')
        self.assertEqual(before['runs'][0]['status'], 'completed')
        engine.start(self.mid); self.wait(engine)
        after = self.store.get(self.mid)
        self.assertEqual(after['status'], 'completed')
        self.assertEqual(len(calls), 10)  # nine steps + one failed attempt
        self.assertEqual(after['runs'][0]['id'], first_id)
        self.assertEqual(len([r for r in after['runs'] if r['phase']=='debate']), 4)
        self.assertEqual(len([r for r in after['runs'] if r['team']=='CBO']), 1)
        with self.assertRaises(ValueError): engine.start(self.mid)

    def test_cancel_and_single_active(self):
        entered = threading.Event()
        def runner(provider, prompt, directory, cancel, emit):
            entered.set(); cancel.wait(3)
            raise Cancelled('cancelled')
        engine = Engine(self.store, runner)
        engine.start(self.mid); self.assertTrue(entered.wait(2))
        with self.assertRaises(ValueError): engine.start(self.mid)
        engine.stop(self.mid); self.wait(engine)
        self.assertEqual(self.store.get(self.mid)['status'], 'cancelled')

    def test_restart_marks_incomplete_and_preserves_snapshot(self):
        self.store.status(self.mid, 'running')
        self.store.begin(self.mid, 'review:기획', '기획', 'codex', 'review')
        restarted = Store(self.tmp.name); restarted.recover()
        m = restarted.get(self.mid)
        self.assertEqual(m['status'], 'interrupted')
        self.assertEqual(m['runs'][0]['status'], 'interrupted')
        self.assertEqual(m['skill'], 'SKILL SNAPSHOT')

    def test_reading_guide_is_separate_and_exportable(self):
        before = self.store.get(self.mid)
        guide = dict(kind='derived-explanation', result=answer(), source_run_ids=[])
        self.store.event(self.mid, 'reading-guide', guide)
        self.assertEqual(public_meeting(self.store, self.mid)['reading_guide'], guide)
        self.assertEqual(self.store.get(self.mid), before)
        self.assertEqual(self.store.all_events(self.mid)[-1]['payload'], guide)

    def test_revision_does_not_overwrite_original(self):
        new = self.store.create('동일 안건', '새 조건', '새로운 증거', 'NEW SKILL', self.mid)
        self.assertEqual(self.store.get(new)['version'], 2)
        self.assertEqual(self.store.get(self.mid)['brief'], '아이템 유지')
        self.assertEqual(self.store.get(new)['parent'], self.mid)

    def test_unknown_evidence_is_rejected(self):
        value = answer(); value['evidence_ids'] = ['E999']
        with self.assertRaises(ValueError): parse_result(json.dumps(value), self.store.get(self.mid))

    def test_review_has_no_other_teams_and_cites_snapshot(self):
        prompt = build_prompt(self.store.get(self.mid), '기획', 'review', [])
        self.assertIn('SKILL SNAPSHOT', prompt)
        self.assertIn('다른 팀의 초안은 제공하지 않는다', prompt)
        self.assertIn('사용자 제공·미검증', prompt)

    def test_export_includes_events_beyond_first_page(self):
        for i in range(530):
            self.store.event(self.mid, 'delta', {'text': str(i)})
        events = self.store.all_events(self.mid)
        self.assertEqual(len(events), 531)
        self.assertEqual(events[-1]['payload']['text'], '529')

    def test_shutdown_joins_active_worker(self):
        entered = threading.Event()
        def runner(provider, prompt, directory, cancel, emit):
            entered.set(); cancel.wait(3)
            raise Cancelled('shutdown')
        engine = Engine(self.store, runner)
        engine.start(self.mid); self.assertTrue(entered.wait(2))
        engine.shutdown()
        self.assertFalse(engine.worker.is_alive())
        self.assertEqual(self.store.get(self.mid)['status'], 'cancelled')

    def test_cli_adapter_parses_real_process_output(self):
        fake = Path(self.tmp.name) / 'fake-cli'
        records = [dict(type='thread.started'), dict(type='item.completed', item=dict(type='agent_message', text=json.dumps(answer()))), dict(type='turn.completed', usage={'output_tokens': 4})]
        fake.write_text('#!'+sys.executable+'\nimport sys,json\nsys.stdin.read()\nfor x in '+repr(records)+': print(json.dumps(x),flush=True)\n')
        fake.chmod(0o700)
        emitted = []
        with patch('server.shutil.which', return_value=str(fake)):
            text, usage = invoke('codex', 'test prompt', Path(self.tmp.name), threading.Event(), lambda k,p: emitted.append(k))
        self.assertEqual(json.loads(text), answer())
        self.assertEqual(usage['output_tokens'], 4)
        self.assertIn('response', emitted)

    def test_cancel_while_process_does_not_read_stdin(self):
        fake = Path(self.tmp.name) / 'blocked-cli'
        fake.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(30)\n')
        fake.chmod(0o700)
        cancel = threading.Event()
        timer = threading.Timer(.2, cancel.set); timer.start()
        started = time.monotonic()
        with patch('server.shutil.which', return_value=str(fake)):
            with self.assertRaises(Cancelled):
                invoke('codex', 'x'*200000, Path(self.tmp.name), cancel, lambda *args: None)
        timer.join()
        self.assertLess(time.monotonic()-started, 5)

    def test_http_write_requires_local_origin_and_token(self):
        handler = make_handler(self.store, None, 'expected', 8765)
        rejected = []
        request = SimpleNamespace(headers={'Host':'127.0.0.1:8765','Origin':'https://elsewhere.example','X-Council-Token':'expected'}, respond=lambda *a: rejected.append(a))
        self.assertFalse(handler.permitted(request, write=True))
        request.headers['Origin']='http://127.0.0.1:8765'
        request.headers['X-Council-Token']='wrong'
        self.assertFalse(handler.permitted(request, write=True))
        request.headers['X-Council-Token']='expected'
        self.assertTrue(handler.permitted(request, write=True))

def member_answer(member, phase, reports):
    value = answer()
    value['summary'] = f"{phase}:{member['id']}의 독립 의견"
    if member['team'] != 'CBO':
        value['perspectives'] = [dict(role=member['role'], view=value['summary'])]
    else:
        value['perspectives'] = [dict(role=role, view='검증용 팀 판단') for role in ['종합','사업','기획','개발','디자인']]
        value['next_steps'] = ['담당: 사업 | 할 일: 공급 조건 확인 | 전달할 자료: 견적 | 받는 팀: 전원 | 다음 단계 조건: 조건 확인'] * 3
    targets = [r for r in reports if r.get('member_id') != member['id'] and 'member_id' in r]
    if phase != 'review' and targets:
        target = targets[0]
        value['challenges'] = [dict(target=target['member_id'], claim=target['result']['summary'], response='근거 E1 검증 전에는 보류')]
    return value


def tagged_json(prompt, tag):
    return json.loads(prompt.split(f'<{tag}>', 1)[1].split(f'</{tag}>', 1)[0])


class IndependentMemberTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.mid = self.store.create('동일 안건', '아이템 유지', '공급 조건 미확인', 'SKILL SNAPSHOT')

    def tearDown(self):
        self.tmp.cleanup()

    def wait(self, engine):
        until = time.monotonic() + 10
        while engine.active and time.monotonic() < until:
            time.sleep(.01)
        self.assertIsNone(engine.active)

    def execute(self, fail_once=None):
        calls = []
        failed = False
        def runner(provider, prompt, directory, cancel, emit):
            nonlocal failed
            identity = tagged_json(prompt, 'identity')
            reports = tagged_json(prompt, 'prior_reports')
            run = self.store.get(self.mid)['runs'][-1]
            calls.append(dict(identity=identity, reports=reports, provider=provider,
                              directory=directory, phase=run['phase'], run=run, prompt=prompt))
            if run['step'] == fail_once and not failed:
                failed = True
                raise RuntimeError('isolated member failure')
            return json.dumps(member_answer(identity, run['phase'], reports)), {'output_tokens': 1}
        return Engine(self.store, runner), calls

    def test_lite_has_four_independent_representatives_and_nine_calls(self):
        self.mid = self.store.create('간단 안건', '조건 유지', '근거', 'SKILL', protocol='lite-v1')
        engine, calls = self.execute()
        engine.start(self.mid); self.wait(engine)
        meeting = self.store.get(self.mid)
        self.assertEqual(meeting['status'], 'completed', meeting['runs'][-1]['error'])
        self.assertEqual(len(calls), 9)
        self.assertEqual(len(meeting['roster']), 5)
        for call in calls:
            if call['phase'] == 'review':
                self.assertEqual(call['reports'], [])
            elif call['phase'] == 'debate':
                self.assertEqual(len(call['reports']), 4)
                self.assertEqual({r['phase'] for r in call['reports']}, {'review'})
                self.assertEqual({r['team'] for r in call['reports']}, {'기획','사업','디자인','개발'})
            else:
                self.assertEqual(len(call['reports']), 8)
        self.assertFalse(any(c['phase']=='internal' for c in calls))
        with self.assertRaises(ValueError):
            self.store.create('bad', 'bad', '', 'SKILL', protocol='unknown')

    def test_lite_retry_preserves_completed_member_runs(self):
        self.mid = self.store.create('간단 안건', '조건 유지', '근거', 'SKILL', protocol='lite-v1')
        engine, calls = self.execute(fail_once='debate:business-1')
        engine.start(self.mid); self.wait(engine)
        self.assertEqual(self.store.get(self.mid)['status'], 'failed')
        saved = {r['id'] for r in self.store.get(self.mid)['runs'] if r['status']=='completed'}
        engine.start(self.mid); self.wait(engine)
        meeting = self.store.get(self.mid)
        self.assertEqual(meeting['status'], 'completed')
        self.assertEqual(len(calls), 10)
        self.assertTrue(saved.issubset({r['id'] for r in meeting['runs']}))

    def test_full_meeting_has_20_independent_members_and_frozen_debate_contexts(self):
        engine, calls = self.execute()
        engine.start(self.mid); self.wait(engine)
        meeting = self.store.get(self.mid)
        self.assertEqual(meeting['status'], 'completed', meeting['runs'][-1]['error'])
        self.assertEqual(meeting['protocol'], 'members-v2')
        self.assertEqual(meeting['roster'], ROSTER + [CBO])
        self.assertEqual(len(calls), 61)
        self.assertEqual(len({c['directory'] for c in calls}), 61)
        results = {(r['phase'], r['member_id']): r['result'] for r in meeting['runs']}
        for phase in ('review', 'internal', 'debate'):
            phase_calls = [c for c in calls if c['phase'] == phase]
            self.assertEqual({c['identity']['id'] for c in phase_calls}, {m['id'] for m in ROSTER})
            self.assertEqual(len(phase_calls), 20)
        for call in calls:
            identity, reports, phase, run = (call[k] for k in ('identity', 'reports', 'phase', 'run'))
            self.assertEqual(call['provider'], identity['provider'])
            self.assertEqual(run['member_id'], identity['id'])
            self.assertEqual(run['member_role'], identity['role'])
            self.assertEqual(run['team'], identity['team'])
            self.assertEqual((call['directory'] / 'prompt.txt').read_text(), call['prompt'])
            self.assertTrue((call['directory'] / 'response.txt').is_file())
            self.assertIn('SKILL SNAPSHOT', call['prompt'])
            self.assertEqual(tagged_json(call['prompt'], 'untrusted_brief')['brief'], '아이템 유지')
            if phase == 'review':
                self.assertEqual(reports, [])
            elif phase == 'internal':
                self.assertEqual(len(reports), 5)
                self.assertEqual({r['team'] for r in reports}, {identity['team']})
                self.assertEqual({r['phase'] for r in reports}, {'review'})
                self.assertEqual({r['member_id'] for r in reports}, {m['id'] for m in ROSTER if m['team'] == identity['team']})
            elif phase == 'debate':
                self.assertEqual(len(reports), 21)
                reviews = [r for r in reports if r['phase'] == 'review']
                self.assertEqual([r['member_id'] for r in reviews], [identity['id']])
                internal = [r for r in reports if r['phase'] == 'internal']
                self.assertEqual({r['member_id'] for r in internal}, {m['id'] for m in ROSTER})
                self.assertFalse(any(r['phase'] == 'debate' for r in reports))
            else:
                self.assertEqual(identity, CBO)
                self.assertEqual(len(reports), 60)
                self.assertEqual({(r['phase'], r['member_id']) for r in reports}, {(p,m['id']) for p in ('review','internal','debate') for m in ROSTER})
            for report in reports:
                self.assertEqual(report['result'], results[report['phase'], report['member_id']])
        frozen = [[r for r in c['reports'] if r['phase']=='internal'] for c in calls if c['phase']=='debate']
        self.assertTrue(all(context == frozen[0] for context in frozen))
        started = [e for e in self.store.all_events(self.mid) if e['kind']=='run.started']
        self.assertEqual(len(started), 61)
        for event, call in zip(started, calls):
            self.assertEqual(event['payload']['member_id'], call['identity']['id'])
            self.assertEqual(event['payload']['member_role'], call['identity']['role'])

    def test_retry_only_failed_member_and_retains_completed_siblings(self):
        engine, calls = self.execute('internal:business-3')
        engine.start(self.mid); self.wait(engine)
        before = self.store.get(self.mid)
        self.assertEqual(before['status'], 'failed')
        completed_ids = [r['id'] for r in before['runs'] if r['status']=='completed']
        self.assertEqual(before['runs'][-1]['member_id'], 'business-3')
        self.assertFalse(any(c['phase']=='decision' for c in calls))
        engine.start(self.mid); self.wait(engine)
        after = self.store.get(self.mid)
        self.assertEqual(after['status'], 'completed', after['runs'][-1]['error'])
        self.assertEqual(len(calls), 62)
        self.assertEqual([r['id'] for r in after['runs'] if r['status']=='completed'][:len(completed_ids)], completed_ids)
        retried = [r for r in after['runs'] if r['step']=='internal:business-3']
        self.assertEqual([r['attempt'] for r in retried], [1,2])
        self.assertEqual([r['status'] for r in retried], ['failed','completed'])
        self.assertEqual(len(calls[-1]['reports']), 60)

    def test_invalid_member_references_and_invented_initial_changes_rejected(self):
        member = ROSTER[0]
        reports = [dict(member_id=m['id'], result=answer()) for m in ROSTER[:5]]
        meeting = self.store.get(self.mid)
        for target in ('unknown-person', member['id'], 'business-1'):
            with self.subTest(target=target):
                value = member_answer(member, 'review', [])
                value['challenges'] = [dict(target=target, claim='claim', response='response')]
                with self.assertRaises(ValueError):
                    parse_result(json.dumps(value), meeting, member, 'internal', reports)
        value = member_answer(member, 'review', [])
        value['changes'] = [dict(before='invented prior view', after='new view', reason='reason', evidence_ids=['E1'])]
        with self.assertRaises(ValueError):
            parse_result(json.dumps(value), meeting, member, 'review', [])
        value = member_answer(member, 'internal', reports)
        self.assertEqual(parse_result(json.dumps(value), meeting, member, 'internal', reports), value)

    def test_cbo_requires_all_teams_and_action_handoffs(self):
        meeting = self.store.get(self.mid)
        good = member_answer(CBO, 'decision', [])
        self.assertEqual(parse_result(json.dumps(good), meeting, CBO, 'decision', []), good)
        bad = json.loads(json.dumps(good))
        bad['perspectives'][4]['role'] = '종합'
        with self.assertRaises(ValueError):
            parse_result(json.dumps(bad), meeting, CBO, 'decision', [])
        bad = json.loads(json.dumps(good))
        bad['next_steps'][0] = '검증 필요'
        with self.assertRaises(ValueError):
            parse_result(json.dumps(bad), meeting, CBO, 'decision', [])
        # Historical saved response is still readable with the original parser contract.
        parse_result(json.dumps(answer()), meeting)
        for protocol in ('lite-v1', 'members-v2'):
            meeting['protocol'] = protocol
            prompt = member_prompt(meeting, CBO, 'decision', [])
            self.assertIn('처음 읽는 사람도 이해할 쉬운 한국어', prompt)
            self.assertIn('이 순서는 고정 절차가 아니다', prompt)
            self.assertGreater(prompt.index('[CBO 결론 작성]'), prompt.index('</skill>'))

    def test_old_schema_migration_preserves_original_protocol_and_data(self):
        legacy_path = Path(self.tmp.name) / 'legacy'
        legacy_path.mkdir()
        with closing(sqlite3.connect(legacy_path / 'council.sqlite3')) as db:
            db.executescript("""
                CREATE TABLE meetings(id TEXT PRIMARY KEY,title TEXT NOT NULL,brief TEXT NOT NULL,evidence TEXT NOT NULL,parent TEXT,version INTEGER NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL,skill TEXT NOT NULL,skill_hash TEXT NOT NULL);
                CREATE TABLE runs(id TEXT PRIMARY KEY,meeting TEXT NOT NULL,step TEXT NOT NULL,team TEXT NOT NULL,provider TEXT NOT NULL,phase TEXT NOT NULL,attempt INTEGER NOT NULL,status TEXT NOT NULL,started TEXT NOT NULL,ended TEXT,result TEXT,error TEXT,usage TEXT,UNIQUE(meeting,step,attempt));
            """)
            db.execute('INSERT INTO meetings VALUES(?,?,?,?,?,?,?,?,?,?)', ('old','old title','old brief','[]',None,1,'completed','2026-10-28','old skill','hash'))
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', ('run','old','review:기획','기획','codex','review',1,'completed','2026-10-28','2026-10-28',json.dumps(answer()),None,None))
            db.commit()
        migrated = Store(legacy_path).get('old')
        self.assertEqual(migrated['protocol'], 'teams-v1')
        self.assertEqual(migrated['roster'], [])
        self.assertEqual(migrated['brief'], 'old brief')
        self.assertEqual(migrated['runs'][0]['result'], answer())
        self.assertIsNone(migrated['runs'][0]['member_id'])
        self.assertEqual(migrated['status'], 'completed')

if __name__ == '__main__': unittest.main()
