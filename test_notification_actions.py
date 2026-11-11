#!/usr/bin/env python3
"""Regression tests without a graphical session or real shutdown calls."""

import ast
from datetime import datetime, timedelta
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


def load_daemon_class():
    # Load the actual class without importing GTK/DBus or starting the daemon.
    path = Path(__file__).with_name('poweroff-daemon.py')
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    tree.body = [node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == 'PoweroffDaemon']
    namespace = {'timedelta': timedelta, 'logger': logging.getLogger(__name__)}
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace['PoweroffDaemon'], namespace


class NotificationActionsTest(unittest.TestCase):
    def setUp(self):
        daemon_class, self.namespace = load_daemon_class()
        self.daemon = daemon_class.__new__(daemon_class)
        self.daemon.shutdown_time = datetime(2026, 11, 11, 18, 0)
        self.daemon.extend_minutes = 30
        self.daemon.interactive = True
        self.daemon.warned = True
        self.daemon.update_indicator = Mock()
        self.notification = Mock()
        self.actions = {}

        def add_action(action, label, callback, user_data=None):
            self.actions[action] = (callback, user_data)

        self.notification.add_action.side_effect = add_action
        self.factory = Mock(return_value=self.notification)
        self.namespace['Notify'] = SimpleNamespace(
            Notification=SimpleNamespace(new=self.factory),
            Urgency=SimpleNamespace(CRITICAL=2),
        )
        self.daemon.show_warning_notification(10)

    def invoke_action(self, action):
        callback, user_data = self.actions[action]
        # Notify.ActionCallback supplies notification, action and user_data.
        callback(self.notification, action, user_data)

    def test_notification_extend_moves_deadline_and_refreshes_indicator(self):
        self.invoke_action('extend')
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 18, 30))
        self.assertFalse(self.daemon.warned)
        self.daemon.update_indicator.assert_called_once_with()
        self.assertEqual(self.factory.call_args.args[0], 'Время продлено')

    def test_ok_accepts_callback_arguments_without_extending(self):
        self.invoke_action('ok')
        self.assertIsNone(self.daemon.warning_notification)
        self.notification.close.assert_called_once_with()
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 18, 0))
        self.daemon.update_indicator.assert_not_called()

    def test_closed_notification_releases_reference(self):
        self.assertIs(self.daemon.warning_notification, self.notification)
        self.notification.connect.assert_called_once_with(
            'closed', self.daemon.warning_notification_closed)
        self.daemon.warning_notification_closed(self.notification)
        self.assertIsNone(self.daemon.warning_notification)
        self.invoke_action('extend')
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 18, 0))

    def test_duplicate_action_does_not_extend_twice(self):
        self.invoke_action('extend')
        self.invoke_action('extend')
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 18, 30))
        self.daemon.update_indicator.assert_called_once_with()

    def test_tray_extend_still_moves_deadline(self):
        self.daemon.extend_time(None)
        self.assertEqual(self.daemon.shutdown_time, datetime(2026, 11, 11, 18, 30))
        self.daemon.update_indicator.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
