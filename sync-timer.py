#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Утилита для синхронизации времени из /etc/poweroff.time в systemd timer
Используется администратором для обновления poweroff-schedule.timer
"""

import configparser
import subprocess
import sys
import os
from datetime import datetime, timedelta

CONFIG_PATH = '/etc/poweroff.time'
TIMER_NAME = 'poweroff-schedule.timer'


def read_default_config():
    """Читает shutdown_time и days из секции [default] конфига"""
    if not os.path.exists(CONFIG_PATH):
        print(f"Ошибка: файл {CONFIG_PATH} не найден", file=sys.stderr)
        return None, None

    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH, encoding='utf-8')

        if 'default' not in config:
            print(f"Ошибка: секция [default] не найдена в {CONFIG_PATH}", file=sys.stderr)
            return None, None

        shutdown_time = config['default'].get('shutdown_time', '').strip()
        if not shutdown_time:
            print(f"Ошибка: параметр shutdown_time не задан в [default]", file=sys.stderr)
            return None, None

        # Читаем дни недели (по умолчанию все дни)
        days_str = config['default'].get('days', '1,2,3,4,5,6,7').strip()
        active_days = [int(d.strip()) for d in days_str.split(',') if d.strip()]

        return shutdown_time, active_days

    except Exception as e:
        print(f"Ошибка чтения конфига: {e}", file=sys.stderr)
        return None, None


def calculate_oncalendar(shutdown_time, active_days):
    """
    Вычисляет OnCalendar для systemd timer с учётом дней недели.
    Возвращает строку вида: "Mon,Tue,Wed,Thu,Fri *-*-* 18:00:00"
    """
    # Преобразуем номера дней (1=Пн, 7=Вс) в названия для systemd
    day_names = {
        1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu',
        5: 'Fri', 6: 'Sat', 7: 'Sun'
    }

    if not active_days or len(active_days) == 7:
        # Все дни - упрощённый формат
        return f"*-*-* {shutdown_time}:00"

    # Только определённые дни
    days_list = ','.join([day_names[d] for d in sorted(active_days) if d in day_names])
    return f"{days_list} *-*-* {shutdown_time}:00"


def update_timer(oncalendar_value):
    """Обновляет OnCalendar в systemd timer через systemctl edit"""
    override_conf = f"""[Timer]
OnCalendar=
OnCalendar={oncalendar_value}
Persistent=false
"""

    override_dir = f'/etc/systemd/system/{TIMER_NAME}.d'
    override_file = f'{override_dir}/override.conf'

    try:
        # Создаём директорию для drop-in
        os.makedirs(override_dir, exist_ok=True)

        # Пишем override.conf
        with open(override_file, 'w') as f:
            f.write(override_conf)

        print(f"✓ Создан {override_file}")

        # Перезагружаем systemd
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        print("✓ systemd daemon-reload выполнен")

        # Рестарт таймера (если он был запущен)
        result = subprocess.run(['systemctl', 'is-enabled', TIMER_NAME],
                              capture_output=True, text=True)
        if result.returncode == 0:
            subprocess.run(['systemctl', 'restart', TIMER_NAME], check=True)
            print(f"✓ Таймер {TIMER_NAME} перезапущен")

        # Показываем статус
        subprocess.run(['systemctl', 'status', TIMER_NAME, '--no-pager'], check=False)

        return True

    except Exception as e:
        print(f"Ошибка обновления таймера: {e}", file=sys.stderr)
        return False


def main():
    if os.geteuid() != 0:
        print("Ошибка: требуются права root (или sudo)", file=sys.stderr)
        sys.exit(1)

    print(f"Чтение времени выключения из {CONFIG_PATH}...")
    shutdown_time, active_days = read_default_config()

    if not shutdown_time:
        sys.exit(1)

    print(f"Найдено время: {shutdown_time}")
    if active_days and len(active_days) < 7:
        day_names = {1: 'Пн', 2: 'Вт', 3: 'Ср', 4: 'Чт', 5: 'Пт', 6: 'Сб', 7: 'Вс'}
        days_str = ', '.join([day_names[d] for d in sorted(active_days)])
        print(f"Активные дни: {days_str}")
    else:
        print(f"Активные дни: каждый день")

    oncalendar = calculate_oncalendar(shutdown_time, active_days)
    print(f"\nОбновление {TIMER_NAME}...")
    print(f"OnCalendar={oncalendar}")

    if update_timer(oncalendar):
        print(f"\n✓ Таймер успешно обновлён")
        print(f"\nДля включения/выключения таймера используйте:")
        print(f"  systemctl enable --now {TIMER_NAME}")
        print(f"  systemctl disable --now {TIMER_NAME}")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
