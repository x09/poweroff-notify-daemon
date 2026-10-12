# Poweroff Notify Daemon v1

## Краткое описание

Решение для автоматического выключения Linux-станций в корпоративной среде с GUI-уведомлениями и двухуровневой защитой от обхода.

## Компоненты

1. **poweroff-daemon.py** — Python-демон с GTK3/AppIndicator3
2. **poweroff-daemon.desktop** — XDG autostart (запуск при логине)
3. **poweroff-schedule.timer** — systemd timer (резервное выключение)
4. **sync-timer.py** — утилита синхронизации времени из конфига в таймер
5. **install.sh / uninstall.sh** — скрипты установки/удаления

## Быстрый старт

```bash
# Установка
sudo ./install.sh

# Редактирование конфига
sudo nano /etc/poweroff.time

# Перелогиньтесь - демон запустится автоматически
```

## Защита от обхода

- **Уровень 1:** XDG autostart (запускается при входе каждого пользователя)
- **Уровень 2:** System timer от root (пользователь не может отключить)

## Управление через GPO/Samba AD

Конфигурация поддерживает три уровня правил с приоритетами:

1. **[default]** — базовые настройки для всех пользователей
2. **[group:имягруппы]** — правила для доменных групп (переопределяют `[default]`)
3. **[user:username]** — персональные настройки (переопределяют `[group:*]` и `[default]`)

Пример:
```ini
[default]
shutdown_time = 18:00

[group:developers]
shutdown_time = 20:00

[group:admins]
shutdown_time = none  # Отключить для группы

[user:ivanov.aa]
shutdown_time = 19:00  # Персональное переопределение
```

## Технологии

- Python 3
- GTK3 + AyatanaAppIndicator3 (GNOME 48+, KDE, MATE)
- systemd (timer для резервного выключения)
- DBus (systemd-logind для выключения)

## Документация

См. [README.md](README.md) для полной документации.
