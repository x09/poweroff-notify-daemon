#!/usr/bin/env python3
"""Integration check on a PRIVATE bus: dbus-run-session -- python3 -B test_notify_dbus.py.

Uses real LibNotify and ActionInvoked signals, with a fake notification server.
Never starts the daemon, a graphical session, or a shutdown operation.
"""
import gc
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from unittest.mock import Mock


def server():
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = dbus.service.BusName('org.freedesktop.Notifications', bus)

    class Notifications(dbus.service.Object):
        serial = 0

        @dbus.service.method('org.freedesktop.Notifications', out_signature='as')
        def GetCapabilities(self):
            return ['actions', 'body']

        @dbus.service.method('org.freedesktop.Notifications', out_signature='ssss')
        def GetServerInformation(self):
            return ('Test server', 'Tests', '1.0', '1.2')

        @dbus.service.method('org.freedesktop.Notifications', in_signature='susssasa{sv}i', out_signature='u')
        def Notify(self, app, replaces, icon, summary, body, actions, hints, timeout):
            self.serial += 1
            return self.serial

        @dbus.service.method('org.freedesktop.Notifications', in_signature='u')
        def CloseNotification(self, ident):
            self.NotificationClosed(ident, 3)

        @dbus.service.signal('org.freedesktop.Notifications', signature='us')
        def ActionInvoked(self, ident, action):
            pass

        @dbus.service.signal('org.freedesktop.Notifications', signature='uu')
        def NotificationClosed(self, ident, reason):
            pass

        @dbus.service.method('org.example.NotificationTest', in_signature='us')
        def Activate(self, ident, action):
            self.ActionInvoked(ident, action)

    service = Notifications(name, '/org/freedesktop/Notifications')
    print('READY', flush=True)
    GLib.MainLoop().run()


def client():
    # Start a fresh session bus even when invoked from the desktop session.
    if '--private-client' not in sys.argv:
        return subprocess.call(['dbus-run-session', '--', sys.executable, '-B',
                                str(Path(__file__).resolve()), '--private-client'])
    import gi
    gi.require_version('Notify', '0.7')
    from gi.repository import Notify, GLib
    import dbus
    from test_notification_actions import load_daemon_class

    process = subprocess.Popen([sys.executable, '-B', __file__, '--server'],
                               stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'READY'
        klass, namespace = load_daemon_class()
        namespace.update(Notify=Notify, GLib=GLib)
        Notify.init('Poweroff integration test')
        daemon = klass.__new__(klass)
        daemon.shutdown_time = datetime(2026, 11, 11, 16, 20)
        daemon.extend_minutes = 30
        daemon.interactive = True
        daemon.warned = True
        daemon.update_indicator = Mock()
        daemon.show_warning_notification(4)
        gc.collect()  # The notification must survive return from the show method.
        bus = dbus.SessionBus()
        proxy = bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
        proxy.Activate(1, 'extend', dbus_interface='org.example.NotificationTest')
        loop = GLib.MainLoop()
        GLib.timeout_add(500, lambda: (loop.quit(), False)[1])
        loop.run()
        assert daemon.shutdown_time == datetime(2026, 11, 11, 16, 50), daemon.shutdown_time
        daemon.update_indicator.assert_called_once_with()
        print('PASS: real LibNotify ActionInvoked extends 16:20 to 16:50 after gc.collect()')
        Notify.uninit()
        return 0
    finally:
        process.terminate()
        process.wait(timeout=5)
        process.stdout.close()


if __name__ == '__main__':
    if '--server' in sys.argv:
        server()
    else:
        sys.exit(client())
