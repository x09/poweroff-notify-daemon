# Changelog

## [1.0.2-alt2] - 2026-11-12

### Fixed
- Reset extensions and recalculate the base deadline on every successful manual
  or periodic configuration reload, matching 1.0.1 behaviour.
- After the base time has passed, schedule the next active day; keep the existing
  deadline if the configuration is invalid.
- Use the notification wording "Выключение DD.MM в HH:MM" and
  "Компьютер выключится через 15 секунд...".
- Update regression tests and documentation for the restored reload behaviour.

## [1.0.2] - 2026-11-11

### Fixed
- Keep notification objects alive until closed so button actions reach the daemon.
- Accept LibNotify user_data in notification action callbacks.
- Preserve shutdown extensions when reloading unchanged effective schedules.
- Validate configuration before applying it; retain previous settings on errors.
- Support inline configuration comments and reject invalid time, day and interval values.
- Replace the blocking final delay with a cancellable 15-second GLib timer.
- Cancel pending shutdown on extension or schedule changes and report shutdown failures.

### Tests
- Add regression tests for notification actions, configuration reload and shutdown scheduling.
- Add a real LibNotify/DBus integration test using an isolated notification server.

The independent fallback systemd timer is unchanged.

## [1.0.0] - 2026-10-08

### Added
- Initial release of Poweroff Notify Daemon
- GUI daemon with AyatanaAppIndicator3 support for system tray
- XDG autostart integration (replaces systemd user service)
- Optional system timer for fallback shutdown (dual-level protection)
- INI-based configuration with flexible rule system:
  - `[default]` — base settings for all users
  - `[group:name]` — domain group rules (override default)
  - `[user:name]` — personal settings (override group and default)
- Priority-based configuration merging (default < group < user)
- Support for `shutdown_time = none` to disable shutdown for specific users/groups
- Days of week scheduling support (1=Mon, 2=Tue, ..., 7=Sun)
- Dynamic tray icons (normal blue / warning red alarm clock)
- Interactive notifications with extend time option
- Case-insensitive username and group name matching
- Compatible with GNOME 48+, KDE, MATE desktop environments
- Custom project icons (SVG + PNG sizes: 16, 24, 32, 48, 64, 128, 256)
- Automatic config reload at specified intervals
- Logging to stdout/stderr (captured by ~/.xsession-errors)

### Fixed
- **CRITICAL**: Prevented immediate shutdown on package install
  - Set `Persistent=false` in systemd timer
  - Enhanced `sync-timer.py` to generate proper `OnCalendar` with weekdays
  - Timer now correctly schedules next occurrence instead of catching up missed runs

### Technical Details
- Language: Python 3
- Dependencies: GTK3, AyatanaAppIndicator3, libnotify
- Shutdown mechanism: systemd-logind via DBus
- Configuration format: INI with section inheritance

### Known Limitations
- GNOME 48+ requires AppIndicator extension for tray icon
- Wayland sessions need `XDG_SESSION_TYPE=wayland` environment variable
- Group membership checked via `groups` command (requires user to be logged in)
