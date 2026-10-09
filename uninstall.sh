#!/bin/bash
# Скрипт удаления poweroff-notify-daemon

set -e

echo "=== Удаление poweroff-notify-daemon ==="

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "Ошибь: запустите скрипт с правами root (sudo)"
    exit 1
fi

# Остановка и отключение systemd user service
echo "Остановка и отключение user service..."
systemctl --global disable poweroff-daemon.service || true

# Остановка всех запущенных экземпляров у всех пользователей
echo "Остановка запущенных процессов..."
pkill -f "poweroff-daemon.py" || true

# Остановка и отключение system timer
echo "Остановка и отключение system timer..."
systemctl stop poweroff-schedule.timer || true
systemctl disable poweroff-schedule.timer || true

# Удаление systemd файлов
echo "Удаление systemd unit файлов..."
rm -f /etc/systemd/user/poweroff-daemon.service
rm -f /etc/systemd/system/poweroff-schedule.timer
rm -f /etc/systemd/system/poweroff-schedule.service
rm -rf /etc/systemd/system/poweroff-schedule.timer.d
systemctl daemon-reload

# Удаление исполняемых файлов
echo "Удаление исполняемых файлов..."
rm -f /usr/bin/poweroff-daemon.py
rm -f /usr/bin/sync-timer.py

# Удаление иконок
echo "Удаление иконок..."
rm -f /usr/share/icons/hicolor/scalable/apps/poweroff-daemon.svg
rm -f /usr/share/icons/hicolor/16x16/apps/poweroff-daemon.png
rm -f /usr/share/icons/hicolor/24x24/apps/poweroff-daemon.png
rm -f /usr/share/icons/hicolor/32x32/apps/poweroff-daemon.png
rm -f /usr/share/icons/hicolor/48x48/apps/poweroff-daemon.png
rm -f /usr/share/icons/hicolor/64x64/apps/poweroff-daemon.png
rm -f /usr/share/icons/hicolor/128x128/apps/poweroff-daemon.png
rm -f /usr/share/icons/hicolor/256x256/apps/poweroff-daemon.png
rm -f /usr/share/pixmaps/poweroff-daemon.png

# Обновление кэша иконок
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    echo "Обновление кэша иконок..."
    gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
fi

# Удаление старого autostart файла (если есть)
rm -f /etc/xdg/autostart/poweroff-daemon.desktop

# Спрашиваем про конфиг
read -p "Удалить конфигурационный файл /etc/poweroff.time? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f /etc/poweroff.time
    echo "Конфигурация удалена."
else
    echo "Конфигурация сохранена."
fi

echo ""
echo "=== Удаление завершено ==="
echo ""
echo "Пользователям нужно перелогиниться для полной остановки сервиса."
echo ""
