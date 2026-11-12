#!/usr/bin/env python3
"""Headless regression tests: no real notifications, timers or shutdown."""
import configparser
from datetime import datetime, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

from test_notification_actions import load_daemon_class


class Clock(datetime):
    current = datetime(2026, 11, 11, 17, 0)

    @classmethod
    def now(cls):
        return cls.current


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        Clock.current = datetime(2026, 11, 11, 17, 0)
        klass, self.namespace = load_daemon_class()
        self.namespace.update(datetime=Clock, os=os, configparser=configparser)
        self.glib = SimpleNamespace(timeout_add_seconds=Mock(return_value=42), source_remove=Mock())
        self.notification_factory = Mock(return_value=Mock())
        self.namespace.update(GLib=self.glib, Notify=SimpleNamespace(
            Notification=SimpleNamespace(new=self.notification_factory),
            Urgency=SimpleNamespace(CRITICAL=2)))
        self.daemon = klass.__new__(klass)
        self.daemon.__dict__.update(
            config={}, username='alice', shutdown_time=None, shutdown_timer_id=None,
            pending_shutdown=None, final_notification=None, extend_minutes=30,
            warn_minutes=10, reload_minutes=15, interactive=True, warned=False,
            active_days=list(range(1, 8)), indicator=Mock(), time_item=Mock(),
            extend_item=Mock(), current_icon_state='normal')
        self.daemon.get_user_groups = Mock(return_value=['developers'])
        self.daemon.show_error_notification = Mock()
        self.daemon.update_icon = Mock()
        self.daemon.perform_shutdown = Mock(return_value=True)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'poweroff.time'
        self.daemon.CONFIG_PATH = str(self.path)
        self.write_config()

    def write_config(self, body='shutdown_time = 18:00\ndays = 1,2,3,4,5', extra=''):
        self.path.write_text('[default]\n' + body + '\n' + extra, encoding='utf-8')

    def load(self):
        self.assertTrue(self.daemon.load_config())

    def test_reload_resets_extension_before_and_after_base_time(self):
        for method in ('manual_reload_config', 'reload_config_timer'):
            for now, expected in (
                (datetime(2026, 11, 11, 17, 55), datetime(2026, 11, 11, 18, 0)),
                (datetime(2026, 11, 11, 18, 25), datetime(2026, 11, 12, 18, 0)),
                (datetime(2026, 11, 13, 18, 25), datetime(2026, 11, 16, 18, 0)),
            ):
                with self.subTest(method=method, now=now):
                    Clock.current = now.replace(hour=17, minute=0)
                    self.load()
                    self.daemon.extend_time(None)
                    self.assertEqual(self.daemon.shutdown_time, now.replace(hour=18, minute=30))
                    Clock.current = now
                    if method == 'manual_reload_config':
                        self.daemon.manual_reload_config(None)
                    else:
                        self.assertTrue(self.daemon.reload_config_timer())
                    self.assertEqual(self.daemon.shutdown_time, expected)

    def test_non_schedule_parameters_reload_resets_deadline_and_updates_menu(self):
        self.load()
        self.daemon.extend_time(None)
        self.write_config('shutdown_time=18:00\ndays=5,4,3,2,1,1\nextend_minutes=45\nwarn_minutes=0\nreload_minutes=2\ninteractive=no')
        self.load()
        self.daemon.update_indicator()
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 18, 0))
        self.assertEqual(self.daemon.reload_minutes, 2)
        self.assertFalse(self.daemon.interactive)
        self.daemon.extend_item.set_label.assert_called_with('Продлить на 45 мин')

    def test_effective_user_rule_shields_against_default_change(self):
        self.write_config(extra='[user:alice]\nshutdown_time=19:00')
        self.load()
        self.daemon.extend_time(None)
        self.write_config('shutdown_time=20:00\ndays=1,2,3,4,5', '[user:alice]\nshutdown_time=19:00')
        self.load()
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 19, 0))

    def test_schedule_change_resets_extension_and_notifies(self):
        self.load()
        self.daemon.extend_time(None)
        self.write_config('shutdown_time=19:00\ndays=4')
        self.load()
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 12, 19, 0))
        self.assertEqual(self.notification_factory.call_args.args[0], 'Расписание изменено')

    def test_invalid_config_preserves_all_settings_and_deadline(self):
        self.load()
        self.daemon.extend_time(None)
        previous = dict(self.daemon.config)
        for value in ('shutdown_time=25:00', 'shutdown_time=none', 'shutdown_time=9:00',
                      'days=', 'days=1,8', 'days=bad', 'days=0',
                      'extend_minutes=0', 'warn_minutes=-1', 'reload_minutes=0',
                      'interactive=treu', 'extend_minutes=1.5', 'reload_minutes=9999999999999'):
            with self.subTest(value=value):
                self.write_config('extend_minutes=40\n' + value if not value.startswith('extend_minutes=') else value)
                self.assertFalse(self.daemon.load_config())
                self.assertEqual(self.daemon.config, previous)
                self.assertEqual(self.daemon.extend_minutes, 30)
                self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 18, 30))
                self.assertIn('[default]', self.daemon.show_error_notification.call_args.args[1])

    def test_invalid_first_load_does_not_schedule_shutdown(self):
        self.write_config('shutdown_time=bad')
        self.assertFalse(self.daemon.load_config())
        self.assertIsNone(self.daemon.shutdown_time)
        self.assertEqual(self.daemon.config, {})

    def test_invalid_unmatched_section_rejects_entire_file(self):
        self.write_config(extra='[user:bob]\nwarn_minutes=-2')
        self.assertFalse(self.daemon.load_config())
        self.assertIn('[user:bob] warn_minutes', self.daemon.show_error_notification.call_args.args[1])

    def test_comments_and_group_none(self):
        self.write_config('shutdown_time=18:00 # comment\ndays=1,2,3 ; comment',
                          '[group:developers]\nshutdown_time=none # disabled')
        self.load()
        self.assertIsNone(self.daemon.shutdown_time)

    def begin_countdown(self):
        self.load()
        Clock.current = datetime(2026, 11, 11, 18, 0, 1)
        self.daemon.update_indicator()
        self.assertEqual(self.glib.timeout_add_seconds.call_args.args[0], 15)
        self.daemon.perform_shutdown.assert_not_called()
        return self.glib.timeout_add_seconds.call_args.args[1:]

    def test_countdown_is_single_without_reload(self):
        callback, deadline = self.begin_countdown()
        self.daemon.update_indicator()
        self.daemon.update_indicator()
        self.glib.timeout_add_seconds.assert_called_once()
        Clock.current += timedelta(seconds=15)
        self.assertFalse(callback(deadline))
        self.daemon.perform_shutdown.assert_called_once_with()
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 12, 18, 0))
        callback(deadline)
        self.daemon.perform_shutdown.assert_called_once_with()

    def test_successful_reload_cancels_final_countdown(self):
        callback, deadline = self.begin_countdown()
        self.daemon.manual_reload_config(None)
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 12, 18, 0))
        self.assertIsNone(self.daemon.shutdown_timer_id)
        callback(deadline)
        self.daemon.perform_shutdown.assert_not_called()

    def test_extension_cancels_countdown_and_stale_callback(self):
        callback, deadline = self.begin_countdown()
        self.daemon.extend_time(None)
        self.glib.source_remove.assert_called_once_with(42)
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 18, 30))
        callback(deadline)
        self.daemon.perform_shutdown.assert_not_called()

    def test_changed_schedule_or_none_cancels_countdown(self):
        for override in ('none', '20:00'):
            with self.subTest(override=override):
                self.setUp_for_countdown_reset()
                callback, deadline = self.begin_countdown()
                self.write_config(extra=f'[user:alice]\nshutdown_time={override}')
                self.load()
                self.assertIsNone(self.daemon.shutdown_timer_id)
                callback(deadline)
                self.daemon.perform_shutdown.assert_not_called()

    def setUp_for_countdown_reset(self):
        self.daemon.cancel_pending_shutdown()
        self.daemon.config = {}
        self.write_config()
        Clock.current = datetime(2026, 11, 11, 17, 0)

    def test_invalid_reload_keeps_countdown_and_reload_timer(self):
        self.begin_countdown()
        self.write_config('reload_minutes=0')
        self.assertTrue(self.daemon.reload_config_timer())
        self.assertEqual(self.daemon.shutdown_timer_id, 42)
        self.glib.source_remove.assert_not_called()
        self.notification_factory.reset_mock()
        self.daemon.manual_reload_config(None)
        self.notification_factory.assert_not_called()

    def test_failed_shutdown_reports_error_without_retry_loop(self):
        callback, deadline = self.begin_countdown()
        self.daemon.perform_shutdown.return_value = False
        Clock.current += timedelta(seconds=15)
        callback(deadline)
        self.daemon.show_error_notification.assert_called_once()
        self.daemon.update_indicator()
        self.daemon.perform_shutdown.assert_called_once()
        self.glib.timeout_add_seconds.assert_called_once()
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 12, 18, 0))

    def test_extension_across_midnight_survives_inactive_day_and_resets_next_cycle(self):
        Clock.current = datetime(2026, 11, 13, 23, 0)
        self.write_config('shutdown_time=23:50\ndays=5')
        self.load()
        self.daemon.extend_time(None)
        Clock.current = datetime(2026, 11, 14, 0, 10)
        self.daemon.update_indicator()
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 14, 0, 20))
        Clock.current = datetime(2026, 11, 14, 0, 20, 1)
        self.daemon.update_indicator()
        callback, deadline = self.glib.timeout_add_seconds.call_args.args[1:]
        Clock.current += timedelta(seconds=15)
        callback(deadline)
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 20, 23, 50))


if __name__ == '__main__':
    unittest.main()
