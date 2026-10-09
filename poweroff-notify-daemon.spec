Name: poweroff-notify-daemon
Version: 1.0.0
Release: alt1

Summary: Daemon for scheduled PC shutdown with GUI notifications
Summary(ru_RU.UTF-8): Демон запланированного выключения ПК с GUI-уведомлениями

License: GPL-3.0-or-later
Group: System/Configuration/Other
Url: https://github.com/x09/poweroff-notify-daemon

Packager: Anton Shevtsov <shevtsov.anton@gmail.com>

Source: %name-%version.tgz

BuildArch: noarch

# Зависимости времени сборки
BuildRequires(pre): rpm-build-python3

# Зависимости времени выполнения
Requires: python3
Requires: python3-module-pygobject3
Requires: libayatana-appindicator3-gir
Requires: libnotify-gir
Requires: systemd
Requires: polkit

%description
Poweroff Notify Daemon provides scheduled PC shutdown functionality
with system tray indicator, countdown timer, and interactive notifications.

Features:
- System tray icon with countdown timer
- User notifications with ability to extend shutdown time
- Per-user configuration via INI file
- Two-level protection: XDG autostart + optional system timer
- Compatible with GNOME 48+, KDE, MATE (via AppIndicator3)
- Centralized management via GPO/Samba AD

%description -l ru_RU.UTF-8
Poweroff Notify Daemon обеспечивает функциональность запланированного
выключения ПК с индикатором в системном трее, таймером обратного отсчёта
и интерактивными уведомлениями.

Возможности:
- Иконка в системном трее с таймером обратного отсчёта
- Уведомления пользователю с возможностью продлить время выключения
- Персональная конфигурация для каждого пользователя через INI-файл
- Двухуровневая защита: XDG autostart + опциональный system timer
- Совместимость с GNOME 48+, KDE, MATE (через AppIndicator3)
- Централизованное управление через GPO/Samba AD

%prep
%setup

%install
# Основные исполняемые файлы
install -Dm755 poweroff-daemon.py %buildroot%_bindir/poweroff-daemon.py
install -Dm755 sync-timer.py %buildroot%_bindir/sync-timer.py

# Systemd system timer и service
install -Dm644 poweroff-schedule.timer %buildroot%_unitdir/poweroff-schedule.timer
install -Dm644 poweroff-schedule.service %buildroot%_unitdir/poweroff-schedule.service

# Конфигурационный файл (example)
install -Dm644 poweroff.time.example %buildroot%_sysconfdir/poweroff.time

# Desktop file для XDG autostart (запуск при логине)
install -Dm644 poweroff-daemon.desktop %buildroot%_sysconfdir/xdg/autostart/poweroff-daemon.desktop

# Иконки
install -Dm644 icons/poweroff-daemon.svg %buildroot%_iconsdir/hicolor/scalable/apps/poweroff-daemon.svg

for i in 16 24 32 48 64 128 256; do
install -Dm644 icons/poweroff-daemon-${i}.png %buildroot%_iconsdir/hicolor/${i}x${i}/apps/poweroff-daemon.png
done

# Symlink для pixmaps (для старых приложений)
install -dm755 %buildroot%_pixmapsdir
ln -s %_iconsdir/hicolor/48x48/apps/poweroff-daemon.png %buildroot%_pixmapsdir/poweroff-daemon.png

# Документация
install -Dm644 README.md %buildroot%_docdir/%name/README.md
install -Dm644 OVERVIEW.md %buildroot%_docdir/%name/OVERVIEW.md
install -Dm644 LICENSE %buildroot%_docdir/%name/LICENSE

%post
# Обновляем кэш иконок
gtk-update-icon-cache %_iconsdir/hicolor &>/dev/null ||:

# Информируем администратора о необходимости настройки
cat <<EOF
=================================================================
Poweroff Notify Daemon установлен.

GUI-демон запустится автоматически при следующем входе пользователя.

ВАЖНО: System timer НЕ включен автоматически.
Для активации резервного таймера выполните:
  1. Настройте /etc/poweroff.time
  2. /usr/bin/sync-timer.py
  3. systemctl enable --now poweroff-schedule.timer

Документация: %_docdir/%name/
=================================================================
EOF

%preun
# Если это полное удаление (не обновление)
if [ $1 -eq 0 ]; then
    # Останавливаем и отключаем system timer
    systemctl disable --now poweroff-schedule.timer 2>/dev/null ||:
fi

%postun
# Обновляем кэш иконок после удаления
gtk-update-icon-cache %_iconsdir/hicolor &>/dev/null ||:

%files
%doc %_docdir/%name/README.md
%doc %_docdir/%name/OVERVIEW.md
%doc %_docdir/%name/LICENSE

# Исполняемые файлы
%_bindir/poweroff-daemon.py
%_bindir/sync-timer.py

# Systemd system timer (резервное выключение)
%_unitdir/poweroff-schedule.timer
%_unitdir/poweroff-schedule.service

# Конфигурация
%config(noreplace) %_sysconfdir/poweroff.time
%_sysconfdir/xdg/autostart/poweroff-daemon.desktop

# Иконки
%_iconsdir/hicolor/scalable/apps/poweroff-daemon.svg
%_iconsdir/hicolor/16x16/apps/poweroff-daemon.png
%_iconsdir/hicolor/24x24/apps/poweroff-daemon.png
%_iconsdir/hicolor/32x32/apps/poweroff-daemon.png
%_iconsdir/hicolor/48x48/apps/poweroff-daemon.png
%_iconsdir/hicolor/64x64/apps/poweroff-daemon.png
%_iconsdir/hicolor/128x128/apps/poweroff-daemon.png
%_iconsdir/hicolor/256x256/apps/poweroff-daemon.png
%_pixmapsdir/poweroff-daemon.png

%changelog
* Thu Oct 08 2026 Anton Shevtsov <shevtsov.anton@gmail.com> 1.0.0-alt1
- Initial release
- Implemented GUI daemon with AyatanaAppIndicator3 support
- Added XDG autostart for automatic launch on user login
- Added optional system timer for fallback shutdown
- INI-based configuration with per-user section support
- Compatible with GNOME 48+, KDE, MATE
- Case-insensitive username matching
- Custom project icons (SVG + multiple PNG sizes)
- Dual-level protection against user disabling
- Support for 'shutdown_time = none' to disable shutdown for specific users
- Inactive menu items when shutdown is disabled
