# Poweroff Notify Daemon

Демон для Linux (ALT Linux, KDE/MATE/GNOME) с индикацией в системном трее оставшегося времени до выключения ПК.

<img width="1270" height="771" alt="1_2026-10-09_10-56" src="https://github.com/user-attachments/assets/0b49638c-1b44-4815-8bd6-5a253dd365d8" />

<img width="1282" height="772" alt="2_2026-10-09_10-56" src="https://github.com/user-attachments/assets/935551d8-b74a-4361-a77a-921d8e8833be" />

<img width="1276" height="775" alt="3_2026-10-09_10-56" src="https://github.com/user-attachments/assets/4352d680-8ebe-4cd6-9f4a-1511b2589464" />


## Возможности

- **Индикатор в трее** с иконкой будильника на проводе
  - Обычная синяя иконка — когда до выключения больше `warn_minutes`
  - Красная иконка — когда осталось меньше `warn_minutes` (для привлечения внимания)
  - Всплывающая подсказка показывает точное время выключения и оставшееся время
- **Уведомления** за N минут до выключения с возможностью продлить время
- **Дни недели** — настройка выключения только в определённые дни (например, Пн-Пт)
- **Централизованное управление** через конфигурационный файл `/etc/poweroff.time`
- **Персональные настройки** для каждого пользователя
- **Автоматическая перезагрузка** конфигурации без рестарта демона
- **Двухуровневая защита от отключения:**
  - XDG autostart (автоматический запуск при входе пользователя во всех DE)
  - Systemd timer как резервное выключение (независимо от демона, требует root)
- **Совместимость** с KDE, MATE, GNOME 48+ (через AyatanaAppIndicator3)

## Требования

### Системные пакеты (ALT Linux)

```bash
apt-get install python3 python3-module-pygobject3 \
                libayatana-appindicator3-gir \
                libnotify-gir polkit
```

### Зависимости Python

Все необходимые библиотеки поставляются через системные пакеты:
- `gi` (PyGObject3) — GTK3, AppIndicator3, Notify
- `dbus-python` — взаимодействие с systemd-logind

## Установка

### 1. Простой способ

Установить rpm пакет 

`apt-get install poweroff-notify-daemon`

### 2. Ручной способ. Копирование файлов

```bash
# Основной скрипт и утилита синхронизации
sudo cp poweroff-daemon.py /usr/bin/
sudo cp sync-timer.py /usr/bin/
sudo chmod +x /usr/bin/poweroff-daemon.py /usr/bin/sync-timer.py

# XDG autostart (для GUI демона)
sudo mkdir -p /etc/xdg/autostart
sudo cp poweroff-daemon.desktop /etc/xdg/autostart/

# Systemd timer (резервное выключение)
sudo cp poweroff-schedule.timer /usr/lib/systemd/system/
sudo cp poweroff-schedule.service /usr/lib/systemd/system/
sudo systemctl daemon-reload

# Иконки
sudo mkdir -p /usr/share/icons/hicolor/{scalable,16x16,24x24,32x32,48x48,64x64,128x128,256x256}/apps
sudo cp icons/poweroff-daemon.svg /usr/share/icons/hicolor/scalable/apps/
sudo cp icons/poweroff-daemon-warning.svg /usr/share/icons/hicolor/scalable/apps/
for size in 16 24 32 48 64 128 256; do
  sudo cp icons/poweroff-daemon-${size}.png /usr/share/icons/hicolor/${size}x${size}/apps/poweroff-daemon.png
  sudo cp icons/poweroff-daemon-warning-${size}.png /usr/share/icons/hicolor/${size}x${size}/apps/poweroff-daemon-warning.png
done
sudo gtk-update-icon-cache /usr/share/icons/hicolor/

# Конфигурация
sudo cp poweroff.time.example /etc/poweroff.time
sudo chmod 644 /etc/poweroff.time
```

**Или используйте автоматический скрипт:**
```bash
sudo ./install.sh
```

### 3. Настройка конфигурации

Отредактируйте `/etc/poweroff.time`:

```ini
[default]
shutdown_time = 18:00
extend_minutes = 30
warn_minutes = 10
reload_minutes = 15
days = 1,2,3,4,5
interactive = true

[user:ivanov.aa]
shutdown_time = 19:00
extend_minutes = 30
```

### 4. Запуск

#### XDG Autostart (GUI демон)

Автоматически запускается при логине всех пользователей во всех DE (KDE, GNOME, MATE, XFCE и т.д.).

**Ручной запуск для тестирования:**
```bash
/usr/bin/poweroff-daemon.py
```

**Проверка что процесс запущен:**
```bash
ps aux | grep poweroff-daemon.py
```

**Пользователь может отключить через:**
- Настройки автозапуска в DE (KDE System Settings → Autostart, GNOME Tweaks → Startup Applications)
- Или создав файл `~/.config/autostart/poweroff-daemon.desktop` с `Hidden=true`

#### System timer (резервное выключение)

Опциональный таймер, который выключит ПК независимо от демона.

**⚠️ ВАЖНО: Правильный порядок настройки**

1. **Сначала настройте `/etc/poweroff.time`** с нужным временем и днями недели
2. **Затем синхронизируйте конфигурацию:**
   ```bash
   /usr/bin/sync-timer.py
   ```
3. **Проверьте что таймер настроен правильно:**
   ```bash
   systemctl status poweroff-schedule.timer
   ```
4. **Только после проверки включайте таймер:**
   ```bash
   systemctl enable --now poweroff-schedule.timer
   ```

**⚠️ КРИТИЧНО:** Не включайте таймер (`systemctl enable --now`) сразу после установки пакета без проверки конфигурации! Если в `/etc/poweroff.time` указано время, которое уже прошло сегодня, таймер может сработать при следующем активном дне согласно параметру `days`.

**Проверка следующего срабатывания:**
```bash
systemctl list-timers poweroff-schedule.timer
```
Убедитесь что время срабатывания (колонка NEXT) соответствует вашим ожиданиям!

**Отключение таймера:**
```bash
systemctl disable --now poweroff-schedule.timer
```

## Конфигурация

### Формат файла `/etc/poweroff.time`

```ini
[default]
# Время выключения (формат HH:MM, 24 часа)
shutdown_time = 18:00

# Дни недели когда выключение должно работать
# 1=Понедельник, 2=Вторник, ..., 7=Воскресенье
# Если не указано — работает каждый день
# Примеры: 1,2,3,4,5 (Пн-Пт) или 1,3,5 (Пн,Ср,Пт)
days = 1,2,3,4,5

# Минут для продления времени выключения
extend_minutes = 30

# За сколько минут показывать предупреждение
warn_minutes = 10

# Интервал перезагрузки конфига (в минутах)
reload_minutes = 15

# Интерактивный режим (true/false)
# true - systemd-logind запросит подтверждение у активных сессий
# false - принудительное выключение
interactive = true

# Персональные настройки пользователей
[user:ivanov.aa]
shutdown_time = 19:00
days = 1,2,3,4,5,6  # Пн-Сб

[user:admin]
shutdown_time = none  # Отключить автовыключение для этого пользователя
```

### Параметры конфигурации

- `shutdown_time` — время выключения в формате `HH:MM` (24-часовой формат)
  - В секции `[default]` значение `none` **не допускается**
  - В пользовательских секциях `[user:username]` можно указать `none` для полного отключения автовыключения
- `days` — дни недели когда выключение должно работать (формат: `1,2,3,4,5`)
  - `1` = Понедельник, `2` = Вторник, ..., `7` = Воскресенье
  - **Если параметр не указан — работает каждый день** (по умолчанию: `1,2,3,4,5,6,7`)
  - Пример: `days = 1,2,3,4,5` (только рабочие дни Пн-Пт)
  - Пример: `days = 1,3,5` (только Пн, Ср, Пт)
- `extend_minutes` — на сколько минут можно продлить время выключения
- `warn_minutes` — за сколько минут до выключения показать предупреждение
- `reload_minutes` — интервал автоматической перезагрузки конфига (в минутах)
- `interactive` — интерактивный режим выключения (`true`/`false`)

### Персональные настройки

Для каждого пользователя можно создать персональную секцию `[user:username]`, которая переопределит параметры из `[default]`:

```ini
[user:petrov.aa]
shutdown_time = 19:30
extend_minutes = 15
warn_minutes = 5
days = 1,3,5  # Только Пн, Ср, Пт
```

### Персональные настройки пользователей

Секция `[user:username]` переопределяет параметры из `[default]`:

```ini
[user:petrov.aa]
warn_minutes = 5
interactive = false
```

Не указанные параметры наследуются из `[default]`.

#### Отключение выключения для конкретных пользователей

В пользовательских секциях можно установить `shutdown_time = none` для полного отключения автоматического выключения:

```ini
[user:admin]
shutdown_time = none
```

**Важно:**
- Значение `none` допускается **только** в секциях `[user:*]`
- В секции `[default]` значение `none` **запрещено** и вызовет ошибку
- Для таких пользователей:
  - В трее отображается "Выкл. откл."
  - Пункт меню "Продлить время" неактивен (серый)
  - System timer (если включён) также не выключит ПК для этого пользователя

### Управление через GPO (Samba AD)

Конфигурационный файл может редактироваться через групповые политики.

**Примеры политик:**

**Стандартное выключение в 18:00 для всех:**
```ini
[default]
shutdown_time = 18:00
extend_minutes = 30
```

**Продлённое время для отдела разработки:**
```ini
[user:developer1]
shutdown_time = 20:00

[user:developer2]
shutdown_time = 20:00
```

**Полное отключение для администраторов:**
```ini
[user:admin]
shutdown_time = none

[user:sysadmin]
shutdown_time = none
```

## Управление через GPO (Samba AD)

Конфигурационный файл может редактироваться через групповые политики:

1. Создайте GPO для управления `/etc/poweroff.time` (синтаксически это обычный ini файл)
2. Используйте GPO Preferences → Files для распространения конфига
3. Используйте GPO Preferences → Ini для редактирования отдельных секций файла
4. Демон автоматически перезагрузит настройки согласно `reload_minutes`
5. **Синхронизация system timer:** После изменения времени в GPO выполните на сервере:
   ```bash
   /usr/bin/sync-timer.py
   ```
   Или автоматизируйте через cron/ansible

## Защита от отключения пользователем

### Двухуровневая защита

**Уровень 1: XDG Autostart (GUI + Уведомления)**
- Демон запускается автоматически при логине через `/etc/xdg/autostart/poweroff-daemon.desktop`
- Работает во всех DE: KDE, GNOME, MATE, XFCE, Cinnamon, LXDE/LXQt
- Если пользователь убьёт процесс (`pkill`) — демон запустится при следующем логине
- Пользователь **может** отключить через настройки автозапуска DE или удалив `~/.config/autostart/poweroff-daemon.desktop`

**Уровень 2: System timer (резервное выключение)**
- Независимый systemd timer, управляемый только администратором (root)
- Выключает ПК в заданное время **независимо** от состояния демона
- Пользователь **не может** отключить system timer (требуются права root)
- Если демон отключён → выключение произойдёт без предупреждений

### Рекомендации для корпоративной среды

**Сценарий 1: Мягкий контроль (рекомендуется)**
- XDG autostart включён → пользователи видят уведомления, могут продлить время
- System timer **отключён** → пользователи могут полностью отключить выключение
- Подходит для офисов с доверенными сотрудниками

**Сценарий 2: Жёсткий контроль**
- XDG autostart включён → GUI + уведомления
- System timer **включён** → гарантированное выключение в заданное время
- Даже если пользователь отключит демон, ПК всё равно выключится (без предупреждений)
- Подходит для публичных терминалов, учебных классов

### Централизованное управление

**Включение system timer через Ansible/Puppet:**
```yaml
- name: Sync poweroff timer
  command: /usr/bin/sync-timer.py
  
- name: Enable poweroff timer
  systemd:
    name: poweroff-schedule.timer
    enabled: yes
    state: started
```

**Проверка состояния на всех хостах:**
```bash
# XDG autostart (должен быть у всех)
ls -la /etc/xdg/autostart/poweroff-daemon.desktop

# System timer (опционально)
systemctl is-enabled poweroff-schedule.timer
```

## Использование

### Индикатор в трее

- Иконка будильника на проводе (синяя или красная в зависимости от состояния)
- При наведении мыши показывается tooltip с точным временем выключения и оставшимся временем
- Клик правой кнопкой → меню с действиями

### Меню трея

- **Продлить на N мин** — продлевает время выключения
- **Перезагрузить конфиг** — вручную перечитывает `/etc/poweroff.time`
- **Выход** — закрывает демон (⚠️ выключение ПК не произойдёт, если не включён system timer!)

### Уведомления

За `warn_minutes` минут до выключения появляется уведомление с кнопками:
- **Продлить на N мин** — продлевает время
- **ОК** — просто закрывает уведомление

### Иконки в трее

- **Синий будильник** — обычное состояние (время > `warn_minutes`)
- **Красный будильник** — критическое состояние (время ≤ `warn_minutes`)
- При наведении показывается tooltip с точным временем выключения и оставшимся временем

## Логирование

### Демон (запущенный через XDG autostart)

Логи выводятся в stdout/stderr и могут быть перенаправлены:

```bash
# Ручной запуск с логами в консоль
/usr/bin/poweroff-daemon.py

# Или просмотр логов через ~/.xsession-errors (в некоторых DE)
tail -f ~/.xsession-errors | grep poweroff

# Проверка что процесс запущен
ps aux | grep poweroff-daemon.py
```

### System timer
```bash
# Статус таймера
systemctl status poweroff-schedule.timer

# История запусков
journalctl -u poweroff-schedule.service

# Список всех таймеров
systemctl list-timers --all
```

## Механизм выключения

1. **Основной способ:** DBus → `org.freedesktop.login1.Manager.PowerOff()`
2. **Fallback:** `systemctl poweroff`

Если `interactive = true`, polkit может запросить пароль у пользователя (зависит от настроек polkit и членства в группе wheel).

## Известные ограничения

### GNOME 48+

В GNOME 48+ системный трей удалён. Требуется:
- Расширение **AppIndicator and KStatusNotifierItem Support** (устанавливается автоматически в некоторых дистрибутивах)
- Или использование `gnome-shell-extension-appindicator` из репозитория ALT

Проверка:
```bash
gnome-extensions list | grep -i appindicator
```

Если расширение отсутствует:
```bash
apt-get install gnome-shell-extension-appindicator
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
```

### Wayland

AyatanaAppIndicator3 корректно работает в Wayland-сессиях KDE/GNOME.

## Отладка

### Демон не появляется в трее

```bash
# Проверка зависимостей
python3 -c "import gi; gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import AyatanaAppIndicator3; print('OK')"

# Проверка что процесс запущен
ps aux | grep poweroff-daemon.py

# Проверка что XDG autostart файл на месте
ls -la /etc/xdg/autostart/poweroff-daemon.desktop

# Ручной запуск для отладки
/usr/bin/poweroff-daemon.py
```

### Конфиг не загружается

```bash
# Проверка прав доступа
ls -la /etc/poweroff.time

# Проверка синтаксиса
python3 -c "import configparser; c=configparser.ConfigParser(); c.read('/etc/poweroff.time'); print(c.sections())"

# Ручной запуск для отладки
/usr/bin/poweroff-daemon.py
```

### Выключение не работает

```bash
# Проверка прав через polkit
dbus-send --system --print-reply \
  --dest=org.freedesktop.login1 \
  /org/freedesktop/login1 \
  org.freedesktop.login1.Manager.PowerOff boolean:true
```

### System timer не срабатывает

```bash
# Проверка что таймер включён
systemctl is-enabled poweroff-schedule.timer

# Проверка времени следующего запуска
systemctl list-timers poweroff-schedule.timer

# Проверка конфигурации таймера
systemctl cat poweroff-schedule.timer

# Проверка override (где задано время)
cat /etc/systemd/system/poweroff-schedule.timer.d/override.conf

# Пересинхронизация времени
/usr/bin/sync-timer.py
```

### Пользователь отключил демон

```bash
# Проверка что XDG autostart файл на месте (глобальный)
ls -la /etc/xdg/autostart/poweroff-daemon.desktop

# Проверка что пользователь не отключил автозапуск локально
ls -la ~/.config/autostart/poweroff-daemon.desktop

# Если файл существует в ~/.config/autostart/ с Hidden=true - пользователь отключил
cat ~/.config/autostart/poweroff-daemon.desktop | grep Hidden

# Принудительное включение для пользователя (удалить локальное переопределение)
rm -f ~/.config/autostart/poweroff-daemon.desktop

# Ручной запуск (временно, до перелогина)
/usr/bin/poweroff-daemon.py &

# Проверка что system timer работает как fallback
sudo systemctl status poweroff-schedule.timer
```

## Безопасность

- Демон работает от имени пользователя (не root)
- Выключение выполняется через polkit (требует аутентификации или членства в wheel)
- Конфигурационный файл `/etc/poweroff.time` доступен только на чтение пользователям
- Демон запускается через XDG autostart, пользователь может отключить через настройки DE
- System timer защищён от отключения пользователем (требуется root)

## Архитектура решения

```
┌─────────────────────────────────────────────────────────────┐
│ Уровень 1: XDG Autostart (GUI + Уведомления)               │
│ /etc/xdg/autostart/poweroff-daemon.desktop                 │
│ - Запускается для каждого пользователя при логине          │
│ - Показывает трей, уведомления, возможность продлить       │
│ - Может быть отключен пользователем через настройки DE     │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    читает конфигурацию
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Конфигурация: /etc/poweroff.time                           │
│ [default] shutdown_time=18:00                              │
│ [user:ivanov.aa] shutdown_time=19:00                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    синхронизация через
                    /usr/bin/sync-timer.py
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Уровень 2: System Timer (Резервное выключение)             │
│ /etc/systemd/system/poweroff-schedule.timer                │
│ - Управляется только root                                   │
│ - Независим от демона                                       │
│ - Гарантирует выключение даже если демон отключен          │
│ - Опционален (включается администратором)                   │
└─────────────────────────────────────────────────────────────┘
```

## Файловая структура

```
/usr/bin/poweroff-daemon.py          # Основной демон
/usr/bin/sync-timer.py               # Утилита синхронизации времени
/etc/poweroff.time                   # Конфигурация
/etc/xdg/autostart/
  └─ poweroff-daemon.desktop         # XDG autostart (GUI)
/usr/lib/systemd/system/
  ├─ poweroff-schedule.timer         # System timer (резерв)
  ├─ poweroff-schedule.service       # Действие таймера
  └─ poweroff-schedule.timer.d/
      └─ override.conf               # Время срабатывания (создаётся sync-timer.py)
/usr/share/icons/hicolor/
  ├─ scalable/apps/
  │   ├─ poweroff-daemon.svg         # Обычная иконка (SVG)
  │   └─ poweroff-daemon-warning.svg # Критическая иконка (SVG)
  └─ {16x16,24x24,32x32,48x48,64x64,128x128,256x256}/apps/
      ├─ poweroff-daemon.png         # Обычная иконка (PNG)
      └─ poweroff-daemon-warning.png # Критическая иконка (PNG)
```

## Лицензия

GPL-3.0-or-later

## Автор

Anton Shevtsov <shevtsov.anton@gmail.com>
