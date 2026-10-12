#!/usr/bin/env python3
"""
Тестовый скрипт для проверки получения групп пользователя
Использует id -Gn для совместимости с доменными группами
"""

import subprocess
import sys

def test_group_extraction(username):
    """Тестирует получение групп разными способами"""

    print(f"{'='*70}")
    print(f"Тестирование получения групп для: {username}")
    print(f"{'='*70}\n")

    # Способ 1: id -Gn (рекомендуемый)
    print("1. Команда 'id -Gn username':")
    try:
        result = subprocess.run(['id', '-Gn', username],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            groups_str = result.stdout.strip()
            groups = groups_str.split()
            print(f"   Вывод: {groups_str}")
            print(f"   Распарсено {len(groups)} групп:")
            for g in groups:
                print(f"     - {g}")
        else:
            print(f"   ОШИБКА: {result.stderr}")
    except Exception as e:
        print(f"   ИСКЛЮЧЕНИЕ: {e}")

    print()

    # Способ 2: groups (старый способ)
    print("2. Команда 'groups username' (старый способ):")
    try:
        result = subprocess.run(['groups', username],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            groups_line = result.stdout.strip()
            print(f"   Вывод: {groups_line}")
            if ':' in groups_line:
                groups_str = groups_line.split(':', 1)[1].strip()
                groups = groups_str.split()
                print(f"   Распарсено {len(groups)} групп:")
                for g in groups:
                    print(f"     - {g}")
        else:
            print(f"   ОШИБКА: {result.stderr}")
    except Exception as e:
        print(f"   ИСКЛЮЧЕНИЕ: {e}")

    print()

    # Способ 3: id без параметров (полный вывод)
    print("3. Команда 'id username' (полный вывод для справки):")
    try:
        result = subprocess.run(['id', username],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"   {result.stdout.strip()}")
        else:
            print(f"   ОШИБКА: {result.stderr}")
    except Exception as e:
        print(f"   ИСКЛЮЧЕНИЕ: {e}")

    print(f"\n{'='*70}\n")

if __name__ == '__main__':
    import os

    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = os.getenv('USER', 'root')

    test_group_extraction(username)
