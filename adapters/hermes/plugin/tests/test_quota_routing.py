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


class PollerTest(unittest.TestCase):
    def test_shared_lock_cache_history_and_failure(self):
        import fcntl
        import subprocess
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache = home / 'cache'
            cache.mkdir()
            rows = [row(75), row(25, 'Current session', account='claude')]
            history = cache / 'quota-history.jsonl'
            history.write_text(json.dumps(dict(row(95), ts=NOW-21601)) + '\n' +
                               json.dumps(dict(row(70), ts=NOW-600)) + '\n')
            with patch.object(bridge.time, 'time', return_value=NOW), \
                    patch.object(bridge, '_quota_options', return_value=OPTIONS), \
                    patch.object(bridge.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(rows))) as fetch, \
                    patch.dict(sys.modules, {'hermes_cli.plugin_events': None}):
                with (cache / 'quota-status-cache.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    bridge._refresh_quota_cache(home, 180)
                    fetch.assert_not_called()
                bridge._refresh_quota_cache(home, 180)
                stats = cache / 'quota-status-cache.json'
                state = cache / 'quota-routing-state.json'
                self.assertEqual(json.loads(stats.read_text()), rows)
                measured = json.loads(state.read_text())['accounts']['openai']
                self.assertEqual(measured['windows'][0]['burn_per_hour'], 30)
                self.assertEqual(len(history.read_text().splitlines()), 3)
                os.utime(stats, (NOW-169, NOW-169))
                bridge._refresh_quota_cache(home, 180)
                fetch.assert_called_once()
                os.utime(stats, (NOW-180, NOW-180))
                previous = state.read_bytes()
                fetch.side_effect = subprocess.TimeoutExpired('quota-status', 130)
                bridge._refresh_quota_cache(home, 180)
                self.assertEqual(fetch.call_count, 2)
                self.assertEqual(state.read_bytes(), previous)

    def test_active_idle_resume(self):
        # テスト終了時には監視ループを抜ける。実時間の3分を待たず、条件変数の待機境界を調べる。
        from threading import Condition, Event, Thread
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            ticks, idle, stopped = Event(), Event(), Event()
            cond = Condition()
            real_wait = cond.wait
            def wait(timeout=None):
                if timeout is None:
                    idle.set()
                if not stopped.is_set():
                    real_wait(timeout)
                if stopped.is_set():
                    raise StopIteration
            def worker():
                try:
                    bridge._quota_poll()
                except StopIteration:
                    pass
            fetch = Mock(side_effect=lambda *_: ticks.set())
            with patch.dict(os.environ, DOTFILES_HERMES_QUOTA_INTERVAL_SEC='180', DOTFILES_HERMES_QUOTA_ACTIVE_MIN='30'), \
                    patch.object(bridge, '_hermes_home', return_value=home), \
                    patch.object(bridge, '_quota_cond', cond), patch.object(cond, 'wait', wait), \
                    patch.object(bridge, '_quota_schedule', {}), patch.object(bridge, '_refresh_quota_cache', fetch), \
                    patch.object(bridge.time, 'monotonic', return_value=1000) as clock:
                t = Thread(target=worker, daemon=True)
                with patch.object(bridge, '_quota_thread', t):
                    t.start()
                    try:
                        self.assertTrue(idle.wait(1))
                        fetch.assert_not_called()
                        idle.clear()
                        bridge._touch_quota(home)
                        self.assertTrue(ticks.wait(1))
                        ticks.clear()
                        with cond:
                            clock.return_value += 180
                            cond.notify()
                        self.assertTrue(ticks.wait(1))
                        ticks.clear()
                        with cond:
                            clock.return_value += 1800
                            cond.notify()
                        self.assertTrue(idle.wait(1))
                        self.assertEqual(fetch.call_count, 2)
                        bridge._touch_quota(home)
                        self.assertTrue(ticks.wait(1))
                        self.assertEqual(fetch.call_count, 3)
                    finally:
                        with cond:
                            stopped.set()
                            cond.notify()
                        t.join(1)
                    self.assertFalse(t.is_alive())
