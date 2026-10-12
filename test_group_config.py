#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы правил групп в конфигурации
"""

import configparser
import subprocess

def get_user_groups(username):
    """Получает список групп пользователя (имена и GID) через id -Gn и id -G"""
    try:
        # Получаем имена групп
        result_names = subprocess.run(['id', '-Gn', username],
                                     capture_output=True, text=True, timeout=5)
        # Получаем GID групп
        result_gids = subprocess.run(['id', '-G', username],
                                    capture_output=True, text=True, timeout=5)

        if result_names.returncode == 0 and result_gids.returncode == 0:
            groups_names = result_names.stdout.strip().split()
            groups_gids = result_gids.stdout.strip().split()

            # Объединяем имена и GID
            groups = groups_names + groups_gids
            return groups, groups_names, groups_gids
        return [], [], []
    except Exception as e:
        print(f"Ошибка получения групп: {e}")
        return [], [], []

def test_config_priority(config_path, username):
    """Тестирует приоритеты правил для пользователя"""
    print(f"\n{'='*70}")
    print(f"Тестирование конфигурации для пользователя: {username}")
    print(f"{'='*70}\n")

    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    # 1. Загружаем default
    defaults = config['default'] if 'default' in config else {}
    print(f"1. [default] секция:")
    for key, value in defaults.items():
        print(f"   {key} = {value}")

    # 2. Получаем группы пользователя
    user_groups, groups_names, groups_gids = get_user_groups(username)
    print(f"\n2. Пользователь {username} состоит в группах:")
    if groups_names:
        print(f"   Имена групп:")
        for group in groups_names:
            print(f"   - {group}")
    if groups_gids:
        print(f"   GID групп:")
        for gid in groups_gids:
            print(f"   - {gid}")
    if not user_groups:
        print("   (нет групп)")

    # 3. Ищем правила для групп
    group_config = {}
    matched_group = None
    print(f"\n3. Поиск правил для групп:")
    for section in config.sections():
        if section.startswith('group:'):
            group_name = section[6:].strip().lower()
            print(f"   Проверяем секцию [{section}]...")
            if any(g.lower() == group_name for g in user_groups):
                group_config = dict(config[section])
                matched_group = section
                print(f"   ✓ НАЙДЕНО совпадение: пользователь в группе '{group_name}'")
                break
            else:
                print(f"   - пропущено (пользователь не в группе)")

    if group_config:
        print(f"\n   Применены правила из [{matched_group}]:")
        for key, value in group_config.items():
            print(f"   {key} = {value}")
    else:
        print(f"\n   Групповые правила не найдены")

    # 4. Проверяем персональные правила
    user_section = f'user:{username}'
    user_config = {}
    print(f"\n4. Поиск персональных правил [{user_section}]:")
    if user_section in config:
        user_config = dict(config[user_section])
        print(f"   ✓ Найдена секция [{user_section}]:")
        for key, value in user_config.items():
            print(f"   {key} = {value}")
    else:
        print(f"   Персональная секция не найдена")

    # 5. Итоговая конфигурация
    merged_config = dict(defaults)
    merged_config.update(group_config)
    merged_config.update(user_config)

    print(f"\n5. ИТОГОВАЯ конфигурация (default < group < user):")
    print(f"{'='*70}")
    for key in ['shutdown_time', 'extend_minutes', 'warn_minutes', 'reload_minutes', 'days', 'interactive']:
        value = merged_config.get(key, '(не задано)')
        source = 'default'
        if key in user_config:
            source = f'user:{username}'
        elif key in group_config:
            source = matched_group if matched_group else 'group'
        print(f"   {key:20} = {value:20} [из {source}]")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    import sys
    import os

    config_path = '/etc/poweroff.time'

    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = os.getenv('USER', 'root')

    if not os.path.exists(config_path):
        print(f"ОШИБКА: Конфигурационный файл {config_path} не найден!")
        print(f"Использую тестовый пример...")
        config_path = 'poweroff.time.example'

    if os.path.exists(config_path):
        test_config_priority(config_path, username)
    else:
        print(f"ОШИБКА: Файл {config_path} не найден!")
        sys.exit(1)
