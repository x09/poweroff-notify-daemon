#!/bin/bash
# Скрипт установки poweroff-notify-daemon для ALT Linux

set -e

echo "=== Установка poweroff-notify-daemon ==="

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "Ошибка: запустите скрипт с правами root (sudo)"
    exit 1
fi

# Проверка наличия необходимых пакетов
echo "Проверка зависимостей..."
REQUIRED_PACKAGES="python3 python3-module-pygobject3 gir-core libgtk+3 libappindicator3 libnotify gir-notify polkit"
MISSING_PACKAGES=""

for pkg in $REQUIRED_PACKAGES; do
    if ! rpm -q "$pkg" &>/dev/null; then
        MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
    fi
done

if [ -n "$MISSING_PACKAGES" ]; then
    echo "Необходимо установить следующие пакеты:$MISSING_PACKAGES"
    read -p "Установить сейчас? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        apt-get update
        apt-get install -y $MISSING_PACKAGES
    else
        echo "Установка прервана. Установите пакеты вручную и повторите."
        exit 1
    fi
fi

# Копирование исполняемых файлов
echo "Копирование файлов в /usr/bin/..."
cp -f poweroff-daemon.py /usr/bin/
cp -f sync-timer.py /usr/bin/
chmod +x /usr/bin/poweroff-daemon.py /usr/bin/sync-timer.py

# Установка иконок
echo "Установка иконок..."
mkdir -p /usr/share/icons/hicolor/{scalable,16x16,24x24,32x32,48x48,64x64,128x128,256x256}/apps
cp -f icons/poweroff-daemon.svg /usr/share/icons/hicolor/scalable/apps/
cp -f icons/poweroff-daemon-16.png /usr/share/icons/hicolor/16x16/apps/poweroff-daemon.png
cp -f icons/poweroff-daemon-24.png /usr/share/icons/hicolor/24x24/apps/poweroff-daemon.png
cp -f icons/poweroff-daemon-32.png /usr/share/icons/hicolor/32x32/apps/poweroff-daemon.png
cp -f icons/poweroff-daemon-48.png /usr/share/icons/hicolor/48x48/apps/poweroff-daemon.png
cp -f icons/poweroff-daemon-64.png /usr/share/icons/hicolor/64x64/apps/poweroff-daemon.png
cp -f icons/poweroff-daemon-128.png /usr/share/icons/hicolor/128x128/apps/poweroff-daemon.png
cp -f icons/poweroff-daemon-256.png /usr/share/icons/hicolor/256x256/apps/poweroff-daemon.png

# Symlink для pixmaps (совместимость)
mkdir -p /usr/share/pixmaps
ln -sf /usr/share/icons/hicolor/48x48/apps/poweroff-daemon.png /usr/share/pixmaps/poweroff-daemon.png

# Обновление кэша иконок
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    echo "Обновление кэша иконок..."
    gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
fi

# Установка systemd user service (глобально для всех пользователей)
echo "Установка systemd user service..."
mkdir -p /etc/systemd/user
cp -f poweroff-daemon.service /etc/systemd/user/
systemctl --global enable poweroff-daemon.service
echo "✓ User service включен глобально (автозапуск для всех пользователей)"

# Установка systemd system timer (резервное выключение)
echo "Установка systemd timer (резервное выключение)..."
cp -f poweroff-schedule.timer /etc/systemd/system/
cp -f poweroff-schedule.service /etc/systemd/system/
systemctl daemon-reload
echo "✓ System timer установлен (по умолчанию отключен)"

# Установка конфигурационного файла (если его ещё нет)
if [ ! -f /etc/poweroff.time ]; then
    echo "Установка конфигурационного файла /etc/poweroff.time..."
    cp poweroff.time.example /etc/poweroff.time
    chmod 644 /etc/poweroff.time
    echo "ВНИМАНИЕ: Отредактируйте /etc/poweroff.time перед использованием!"
else
    echo "Файл /etc/poweroff.time уже существует, пропускаем..."
fi

echo ""
echo "=== Установка завершена успешно ==="
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Отредактируйте /etc/poweroff.time (задайте время выключения)"
echo ""
echo "2. User service (GUI демон с треем):"
echo "   - Автоматически запустится при следующем логине пользователей"
echo "   - Для немедленного запуска текущему пользователю:"
echo "     systemctl --user start poweroff-daemon.service"
echo ""
echo "3. System timer (резервное выключение - опционально):"
echo "   - Синхронизируйте время из конфига:"
echo "     sudo /usr/bin/sync-timer.py"
echo "   - Включите таймер:"
echo "     sudo systemctl enable --now poweroff-schedule.timer"
echo "   - Проверьте статус:"
echo "     sudo systemctl list-timers poweroff-schedule.timer"
echo ""
echo "Для GNOME 48+ убедитесь, что установлено расширение AppIndicator:"
echo "   apt-get install gnome-shell-extension-appindicator"
echo "   gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com"
echo ""
