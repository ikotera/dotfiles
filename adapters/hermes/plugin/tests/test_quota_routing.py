"""公開プラグインをパスから読み込み、実際の残量や設定には触れない。"""
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bridge_quota_test", ROOT / "__init__.py")
assert spec is not None and spec.loader is not None
bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)
NOW = 1800000000
OPTIONS = ("quick", "standard", "deep", "claude-backup")


def row(used, window="Session", reset: float = NOW + 3600, account="openai"):
    return dict(account=account, window=window, used=used,
                resets=datetime.fromtimestamp(reset, timezone.utc).isoformat())


class AnalysisTest(unittest.TestCase):
    def test_burn_projection(self):
        rows = [row(30)]
        history = [dict(row(20, reset=NOW + 3600.2), ts=NOW - 600),
                   dict(row(5, reset=NOW + 300), ts=NOW - 890)]
        state = bridge.quota.build_state(rows, history, NOW, OPTIONS)
        w = state["accounts"]["openai"]["windows"][0]
        self.assertEqual((w["burn_per_hour"], w["projected"], w["eta_exhaust_min"]), (60, 90, 70))
        self.assertEqual(state["accounts"]["openai"]["level"], "warn")

    def test_levels(self):
        for label, cuts in (("Session", (60, 75, 90)), ("Weekly", (80, 90, 97))):
            for u, level in zip((cuts[0]-1, *cuts), ("ok", "warn", "high", "critical")):
                a = bridge.quota.build_state([row(u, label)], [], NOW)["accounts"]["openai"]
                self.assertEqual(a["level"], level)
        self.assertEqual(bridge.quota.build_state([row(99, reset=NOW)], [], NOW)
                         ["accounts"]["openai"], {"level": "unknown", "windows": []})

    def test_rate_limits(self):
        for age, old, burn, level in ((299, 0, None, "ok"), (901, 0, None, "ok"),
                                      (300, 40, 0, "ok"), (600, 10, 120, "high"),
                                      (300, 0, 360, "critical")):
            a = bridge.quota.build_state([row(30)], [dict(row(old), ts=NOW-age)], NOW)["accounts"]["openai"]
            self.assertEqual((a["windows"][0]["burn_per_hour"], a["level"]), (burn, level))

    def test_policy(self):
        q, s, d, c = OPTIONS
        for o in bridge.quota.LEVELS:
            for cl in bridge.quota.LEVELS:
                busy = cl in ("high", "critical")
                expected = {"ok": (q,s,d,s if busy else c), "unknown": (q,s,d,s if busy else c),
                            "warn": (q,s,s if busy else c,c), "high": (q,s if busy else c,s if busy else c,c),
                            "critical": (q,)*4 if cl == "critical" else (c,)*4}[o]
                m, both = bridge.quota.routing(o, cl)
                self.assertEqual((tuple(m[k] for k in OPTIONS), both), (expected, o == cl == "critical"))
        self.assertEqual(bridge.quota.routing("high", "ok", (s,d))[0], {s:s, d:d})


class HookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        for name, value in (("_hermes_home", lambda: self.home), ("_touch_quota", lambda home: None),
                            ("_quota_options", lambda: OPTIONS), ("_quota_announced", {})):
            self.enterContext(patch.object(bridge, name, value))
        self.clock = self.enterContext(patch.object(bridge.time, 'time', return_value=NOW))
        self.enterContext(patch.dict(os.environ, DOTFILES_HERMES_QUOTA_ROUTING='1'))
        self.save(80)

    def save(self, used, claude=0, now=NOW):
        state = bridge.quota.build_state([row(used), row(claude, 'Current session', account='claude')], [], now)
        path = self.home / 'cache/quota-routing-state.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(state))

    def route(self, args, **kw):
        return bridge._route_delegate(tool_name='delegate_task', args=args, session_id='test', **kw)

    def test_batch_and_single(self):
        tasks = [{"goal":"a"}, {"goal":"b", "option":"deep"}, {"goal":"c", "option":"quick"}]
        result = self.route({'tasks': tasks})
        self.assertEqual([t['option'] for t in result['args']['tasks']], ['claude-backup','claude-backup','quick'])
        self.assertNotIn('option', tasks[0])
        self.assertEqual(self.route({'goal':'a','context':'b'})['args']['tasks'],
                         [{'goal':'a','context':'b','option':'claude-backup'}])
        self.assertIn('standard→claude-backup', (self.home / 'logs/quota-routing.log').read_text())

    def test_no_rewrite(self):
        args = {'goal':'a'}
        for action in ('list','continue','stop','steer'):
            self.assertIsNone(self.route(dict(args, action=action)))
        self.assertIsNone(self.route(args, task_id='sa-0-f00dbabe'))
        self.assertIsNone(self.route(args, parent_session_id='parent'))
        with patch.object(bridge, '_quota_options', return_value=['quick','standard']):
            self.assertIsNone(self.route(args))
        with patch.dict(os.environ, DOTFILES_HERMES_QUOTA_ROUTING='0'):
            self.assertIsNone(self.route(args))
        self.clock.return_value = NOW + 901
        self.assertIsNone(self.route(args))

    def test_reset_between_polls_keeps_weekly_pressure(self):
        rows = [row(99, reset=NOW+30), row(93, 'Weekly')]
        state = bridge.quota.build_state(rows, [], NOW)
        (self.home / 'cache/quota-routing-state.json').write_text(json.dumps(state))
        self.clock.return_value += 31
        result = self.route({'tasks':[{'goal':'a'}, {'goal':'b','option':'quick'}]})
        self.assertEqual([t['option'] for t in result['args']['tasks']], ['claude-backup', 'quick'])

    def test_notices(self):
        def notice(key='a'):
            return bridge._notify_quota(session_id=key)
        self.assertIn('自動で振り替え', notice()['context'])
        self.assertIsNone(notice())
        self.assertIsNotNone(notice('b'))
        self.clock.return_value = NOW + 179
        self.assertIsNone(notice())
        self.clock.return_value += 1
        self.assertIsNotNone(notice())
        self.save(95, 91)
        text = notice()['context']
        for word in ('95%', 'リセット', '後回し'):
            self.assertIn(word, text)
        self.save(30)
        self.assertIsNotNone(notice())
        self.clock.return_value += 181
        self.assertIsNone(notice())

