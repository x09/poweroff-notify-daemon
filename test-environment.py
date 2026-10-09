#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работоспособности poweroff-notify-daemon
Запускать с правами обычного пользователя в графической сессии
"""

import sys
import os

def check_imports():
    """Проверка импорта необходимых модулей"""
    print("=== Проверка Python-модулей ===")

    modules = [
        ('gi', 'PyGObject3'),
        ('configparser', 'Стандартная библиотека Python'),
        ('datetime', 'Стандартная библиотека Python'),
        ('logging', 'Стандартная библиотека Python'),
    ]

    all_ok = True
    for module, desc in modules:
        try:
            __import__(module)
            print(f"✓ {module:20s} - {desc}")
        except ImportError as e:
            print(f"✗ {module:20s} - ОШИБКА: {e}")
            all_ok = False

    # Проверка GI репозиториев
    print("\n=== Проверка GObject Introspection репозиториев ===")
    gi_repos = [
        ('Gtk', '3.0', 'GTK3'),
        ('AyatanaAppIndicator3', '0.1', 'Ayatana AppIndicator3'),
        ('Notify', '0.7', 'LibNotify'),
    ]

    try:
        import gi
        for repo, version, desc in gi_repos:
            try:
                gi.require_version(repo, version)
                __import__(f'gi.repository.{repo}')
                print(f"✓ {repo:20s} {version:5s} - {desc}")
            except (ValueError, ImportError) as e:
                print(f"✗ {repo:20s} {version:5s} - ОШИБКА: {e}")
                all_ok = False
    except ImportError:
        print("✗ PyGObject3 не установлен")
        all_ok = False

    return all_ok

def check_config():
    """Проверка конфигурационного файла"""
    print("\n=== Проверка конфигурации ===")
    config_path = '/etc/poweroff.time'

    if not os.path.exists(config_path):
        print(f"✗ Файл {config_path} не найден")
        return False

    print(f"✓ Файл {config_path} существует")

    try:
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path)

        if 'default' not in config.sections():
            print("✗ Секция [default] не найдена в конфиге")
            return False

        print(f"✓ Секция [default] найдена")

        required_keys = ['shutdown_time', 'extend_minutes', 'warn_minutes', 'reload_minutes']
        for key in required_keys:
            if key in config['default']:
                print(f"  ✓ {key} = {config['default'][key]}")
            else:
                print(f"  ✗ {key} не задан")

        # Проверка пользовательских секций
        user_sections = [s for s in config.sections() if s.startswith('user:')]
        if user_sections:
            print(f"\n✓ Найдено пользовательских секций: {len(user_sections)}")
            for section in user_sections:
                username = section.split(':', 1)[1]
                print(f"  - {username}")

        return True

    except Exception as e:
        print(f"✗ Ошибка чтения конфига: {e}")
        return False

def check_systemd():
    """Проверка systemd units"""
    print("\n=== Проверка systemd ===")

    import subprocess

    # User service
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'status', 'poweroff-daemon.service'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if 'Active: active' in result.stdout:
            print("✓ User service запущен")
        elif 'could not be found' in result.stderr:
            print("✗ User service не установлен")
        else:
            print("⚠ User service установлен, но не запущен")
    except Exception as e:
        print(f"⚠ Не удалось проверить user service: {e}")

    # System timer
    try:
        result = subprocess.run(
            ['systemctl', 'is-enabled', 'poweroff-schedule.timer'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ System timer включён")
        else:
            print("⚠ System timer отключён (это нормально, он опционален)")
    except Exception as e:
        print(f"⚠ Не удалось проверить system timer: {e}")

def check_icons():
    """Проверка наличия иконок"""
    print("\n=== Проверка иконок ===")

    icon_paths = [
        '/usr/share/icons/hicolor/48x48/apps/poweroff-daemon.png',
        '/usr/share/pixmaps/poweroff-daemon.png',
        'icons/poweroff-daemon-48.png',
    ]

    found = False
    for path in icon_paths:
        if os.path.exists(path):
            print(f"✓ Иконка найдена: {path}")
            found = True
            break

    if not found:
        print("⚠ Пользовательские иконки не найдены, будет использована системная")

    return True

def check_environment():
    """Проверка окружения"""
    print("\n=== Проверка окружения ===")

    # Username
    username = (os.getenv('USER') or os.getenv('USERNAME') or 'unknown').lower()
    print(f"✓ Пользователь: {username}")

    # Display
    display = os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY')
    if display:
        print(f"✓ Графическая сессия: {display}")
    else:
        print("✗ DISPLAY/WAYLAND_DISPLAY не установлены")
        return False

    # DBus session
    dbus = os.getenv('DBUS_SESSION_BUS_ADDRESS')
    if dbus:
        print(f"✓ DBus session доступен")
    else:
        print("⚠ DBUS_SESSION_BUS_ADDRESS не установлен")

    return True

def main():
    print("=" * 60)
    print("Тест poweroff-notify-daemon")
    print("=" * 60)

    all_checks = [
        check_imports(),
        check_config(),
        check_environment(),
        check_icons(),
    ]

    check_systemd()

    print("\n" + "=" * 60)
    if all(all_checks):
        print("✓ Все базовые проверки пройдены успешно!")
        print("\nМожно запустить демон:")
        print("  systemctl --user start poweroff-daemon.service")
        print("или")
        print("  /usr/bin/poweroff-daemon.py")
        return 0
    else:
        print("✗ Обнаружены проблемы. Установите недостающие зависимости.")
        print("\nДля ALT Linux:")
        print("  sudo apt-get install python3 python3-module-pygobject3 \\")
        print("                       libgtk+3 libappindicator3-gir libnotify-gir \\")
        print("                       typelib-Gtk-3.0 polkit")
        return 1

if __name__ == '__main__':
    sys.exit(main())
