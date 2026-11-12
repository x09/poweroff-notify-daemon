#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Poweroff Notify Daemon
Отображает в системном трее оставшееся время до выключения ПК,
предупреждает пользователя за N минут и позволяет продлить время.
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
gi.require_version('Notify', '0.7')

from gi.repository import Gtk, GLib, Notify
from gi.repository import AyatanaAppIndicator3 as AppIndicator3
import dbus
import configparser
import os
import sys
from datetime import datetime, timedelta, time as dt_time
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PoweroffDaemon:
    """Основной класс демона управления выключением"""

    CONFIG_PATH = '/etc/poweroff.time'
    ICON_NORMAL = 'poweroff-daemon'
    ICON_WARNING = 'poweroff-daemon-warning'
    ICON_PATHS_NORMAL = [
        '/usr/share/icons/hicolor/scalable/apps/poweroff-daemon.svg',
        '/usr/share/icons/hicolor/48x48/apps/poweroff-daemon.png',
        '/usr/share/pixmaps/poweroff-daemon.png',
        'icons/poweroff-daemon.svg',
        'icons/poweroff-daemon-48.png',
        'system-shutdown'
    ]
    ICON_PATHS_WARNING = [
        '/usr/share/icons/hicolor/scalable/apps/poweroff-daemon-warning.svg',
        'icons/poweroff-daemon-warning.svg',
        'dialog-warning'
    ]

    def __init__(self):
        self.config = {}
        self.shutdown_timer_id = None
        self.pending_shutdown = None
        self.final_notification = None
        self.warning_notification = None
        self.shutdown_time = None
        self.extend_minutes = 30
        self.warn_minutes = 10
        self.reload_minutes = 15
        self.interactive = True
        self.warned = False
        self.active_days = [1, 2, 3, 4, 5, 6, 7]  # По умолчанию все дни недели
        self.current_icon_state = 'normal'  # Текущее состояние иконки

        # Получаем имя текущего пользователя (приводим к нижнему регистру)
        self.username = (os.getenv('USER') or os.getenv('USERNAME') or 'unknown').lower()
        logger.info(f"Запуск демона для пользователя: {self.username}")

        # Инициализация Notify
        Notify.init("Poweroff Daemon")

        # Загружаем конфигурацию
        self.load_config()

        # Создаём индикатор в трее
        self.indicator = AppIndicator3.Indicator.new(
            "poweroff-daemon",
            self.get_icon_path(),
            AppIndicator3.IndicatorCategory.SYSTEM_SERVICES
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.build_menu())

        # Таймер обновления трея
        # Единый секундный таймер также обновляет финальный отсчёт.
        self.update_timer_id = GLib.timeout_add_seconds(1, self.update_indicator)

        # Таймер перезагрузки конфига
        self.reload_timer_id = GLib.timeout_add_seconds(self.reload_minutes * 60, self.reload_config_timer)

        # Первое обновление
        self.update_indicator()

        logger.info("Демон успешно запущен")

    def get_icon_path(self, warning=False):
        """Определяет путь к иконке (ищет в нескольких местах)"""
        paths = self.ICON_PATHS_WARNING if warning else self.ICON_PATHS_NORMAL
        icon_type = "warning" if warning else "normal"

        for path in paths:
            if os.path.exists(path):
                logger.info(f"Используется иконка ({icon_type}): {path}")
                return path

        # Fallback на системную иконку
        fallback = 'dialog-warning' if warning else 'system-shutdown'
        logger.warning(f"Пользовательская иконка не найдена, используется {fallback}")
        return fallback

    def update_icon(self, warning=False):
        """Обновление иконки в трее"""
        new_state = 'warning' if warning else 'normal'

        # Меняем иконку только если состояние изменилось
        if self.current_icon_state != new_state:
            icon_path = self.get_icon_path(warning)
            self.indicator.set_icon(icon_path)
            self.current_icon_state = new_state
            logger.info(f"Иконка изменена на: {new_state}")
        return "system-shutdown"

    def get_user_groups(self):
        """Получает список групп пользователя (имена и GID) через id -Gn и id -G"""
        try:
            import subprocess
            # Получаем имена групп
            result_names = subprocess.run(['id', '-Gn', self.username],
                                         capture_output=True, text=True, timeout=5)
            # Получаем GID групп
            result_gids = subprocess.run(['id', '-G', self.username],
                                        capture_output=True, text=True, timeout=5)

            if result_names.returncode == 0 and result_gids.returncode == 0:
                # Имена групп (могут быть с пробелами, поэтому разбиваются некорректно)
                groups_names = result_names.stdout.strip().split()
                # GID групп (числа, всегда корректно разделены)
                groups_gids = result_gids.stdout.strip().split()

                # Объединяем: возвращаем и имена, и GID (GID как строки)
                groups = groups_names + groups_gids
                logger.info(f"Пользователь {self.username} состоит в группах: {groups_names}")
                logger.info(f"GID групп: {groups_gids}")
                return groups
            return []
        except Exception as e:
            logger.warning(f"Не удалось получить группы пользователя: {e}")
            return []

    def load_config(self):
        """Загрузка конфигурации из /etc/poweroff.time с поддержкой групп"""
        if not os.path.exists(self.CONFIG_PATH):
            logger.error(f"Конфигурационный файл {self.CONFIG_PATH} не найден")
            self.show_error_notification("Конфиг не найден",
                                        f"Файл {self.CONFIG_PATH} отсутствует")
            return False

        try:
            config = configparser.ConfigParser(
                interpolation=None, inline_comment_prefixes=('#', ';'))
            with open(self.CONFIG_PATH, encoding='utf-8') as stream:
                config.read_file(stream)
            if 'default' not in config:
                raise ValueError("Отсутствует секция [default]")
            # Проверяем весь файл до изменения рабочего состояния.
            self.validate_config_values('DEFAULT', config.defaults())
            for section in config.sections():
                self.validate_config_values(section, dict(config[section]))
            defaults = config['default']

            # Получаем группы пользователя
            user_groups = self.get_user_groups()

            # Применяем правила для групп (приоритет 2)
            # Если пользователь состоит в нескольких группах с правилами, применяется первая найденная
            group_config = {}
            for section in config.sections():
                if section.startswith('group:'):
                    group_name = section[6:].strip().lower()  # после 'group:'
                    # Проверяем что пользователь состоит в этой группе (case-insensitive)
                    if any(g.lower() == group_name for g in user_groups):
                        group_config = dict(config[section])
                        logger.info(f"Применены правила группы [{section}]")
                        break  # Используем первую найденную группу

            # Ищем пользовательскую секцию [user:username] (приоритет 3)
            user_section = f'user:{self.username}'
            user_config = config[user_section] if user_section in config else {}

            # Применяем приоритеты: default < group < user
            # Сначала берём из defaults, затем переопределяем из group, затем из user
            merged_config = dict(defaults)
            merged_config.update(group_config)
            merged_config.update(user_config)

            settings = {
                'shutdown_time': '18:00', 'days': [1, 2, 3, 4, 5, 6, 7],
                'extend_minutes': 30, 'warn_minutes': 10,
                'reload_minutes': 15, 'interactive': True,
            }
            settings.update(self.validate_config_values('effective', merged_config))
            old_config = self.config
            old_shutdown = self.shutdown_time
            # Как в 1.0.1: каждое успешное чтение заново назначает базовый срок.
            new_shutdown = (None if settings['shutdown_time'] == 'none' else
                            self.parse_shutdown_time(settings['shutdown_time'], settings['days']))

            self.config = settings
            self.extend_minutes = settings['extend_minutes']
            self.warn_minutes = settings['warn_minutes']
            self.reload_minutes = settings['reload_minutes']
            self.interactive = settings['interactive']
            self.active_days = settings['days']
            self.close_warning_notification()
            self.cancel_pending_shutdown()
            self.shutdown_time = new_shutdown
            self.warned = False
            if old_config and old_shutdown != new_shutdown:
                message = ('Автоматическое выключение отключено' if new_shutdown is None else
                           f"Новое выключение: {new_shutdown:%d.%m %H:%M}. "
                           "Прежнее продление отменено.")
                try:
                    Notify.Notification.new('Расписание изменено', message,
                                            'dialog-information').show()
                except Exception:
                    logger.exception('Не удалось показать изменение расписания')

            logger.info(f"Конфигурация загружена: shutdown_time={self.shutdown_time}, "
                       f"extend={self.extend_minutes}m, warn={self.warn_minutes}m, "
                       f"reload={self.reload_minutes}m, interactive={self.interactive}, "
                       f"active_days={self.active_days}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            self.show_error_notification("Ошибка конфига", str(e))
            return False

    def validate_config_values(self, section, values):
        """Проверяет значения секции, возвращает отдельный словарь без побочных эффектов."""
        result = {}
        for key, raw in values.items():
            value = raw.strip()
            try:
                if key == 'shutdown_time':
                    if value.lower() == 'none':
                        if section != 'effective' and not section.startswith(('group:', 'user:')):
                            raise ValueError('none разрешён только в [group:*] и [user:*]')
                        result[key] = 'none'
                    else:
                        if (len(value) != 5 or value[2] != ':' or
                                not (value[:2] + value[3:]).isascii() or
                                not (value[:2] + value[3:]).isdigit()):
                            raise ValueError('ожидается время HH:MM')
                        result[key] = datetime.strptime(value, '%H:%M').strftime('%H:%M')
                elif key == 'days':
                    result[key] = self.parse_days(value)
                elif key in ('extend_minutes', 'warn_minutes', 'reload_minutes'):
                    number = int(value)
                    minimum = 0 if key == 'warn_minutes' else 1
                    if number < minimum:
                        raise ValueError(f'значение должно быть не меньше {minimum}')
                    if key == 'reload_minutes' and number * 60 > 2**32 - 1:
                        raise ValueError('интервал слишком велик для GLib')
                    if key == 'extend_minutes':
                        # Проверяем, что интервал представим как дата, а не только как int.
                        datetime.now() + timedelta(minutes=number)
                    result[key] = number
                elif key == 'interactive':
                    if value.lower() not in configparser.ConfigParser.BOOLEAN_STATES:
                        raise ValueError('ожидается true/false, yes/no, on/off или 1/0')
                    result[key] = configparser.ConfigParser.BOOLEAN_STATES[value.lower()]
            except (ValueError, OverflowError) as error:
                raise ValueError(f'[{section}] {key} = {raw!r}: {error}') from error
        return result

    def parse_days(self, days_str):
        """Непустой список дней 1–7; ошибочные значения не заменяются всеми днями."""
        days = [int(day.strip()) for day in days_str.split(',')]
        if not days or any(day < 1 or day > 7 for day in days):
            raise ValueError('ожидается непустой список дней от 1 до 7')
        return sorted(set(days))

    def get_weekday_name(self, weekday):
        """Возвращает название дня недели (1=Пн, 7=Вс)"""
        names = {
            1: 'Пн',
            2: 'Вт',
            3: 'Ср',
            4: 'Чт',
            5: 'Пт',
            6: 'Сб',
            7: 'Вс'
        }
        return names.get(weekday, '?')

    def parse_shutdown_time(self, time_str, active_days=None):
        """Ближайшее будущее выключение по базовому расписанию, без продления."""
        active_days = self.active_days if active_days is None else active_days
        clock_time = datetime.strptime(time_str, '%H:%M').time()
        now = datetime.now()
        shutdown_dt = datetime.combine(now.date(), clock_time)
        if shutdown_dt < now:
            shutdown_dt += timedelta(days=1)
        for _ in range(7):
            if shutdown_dt.isoweekday() in active_days:
                return shutdown_dt
            shutdown_dt += timedelta(days=1)
        raise ValueError('Не найден активный день недели')

    def build_menu(self):
        """Построение меню трея"""
        menu = Gtk.Menu()

        # Пункт с информацией о времени
        self.time_item = Gtk.MenuItem(label="Загрузка...")
        self.time_item.set_sensitive(False)
        menu.append(self.time_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Продлить время (неактивно если shutdown_time = none)
        self.extend_item = Gtk.MenuItem(label=f"Продлить на {self.extend_minutes} мин")
        self.extend_item.connect("activate", self.extend_time)
        menu.append(self.extend_item)

        # Перезагрузить конфиг
        reload_item = Gtk.MenuItem(label="Перезагрузить конфиг")
        reload_item.connect("activate", self.manual_reload_config)
        menu.append(reload_item)

        # Убрана кнопка "Выход" для корпоративной среды
        # Демон должен работать постоянно

        menu.show_all()
        return menu

    def update_indicator(self):
        """Обновление индикатора в трее"""
        if not self.shutdown_time:
            # Выключение отключено для этого пользователя
            self.indicator.set_label("", "")
            tooltip = "Автоматическое выключение отключено"
            self.indicator.set_title(tooltip)
            if self.time_item:
                self.time_item.set_label(tooltip)
            self.update_icon(warning=False)  # Обычная иконка
            self.update_menu_state()
            return True

        now = datetime.now()
        time_left = (self.shutdown_time - now).total_seconds()

        if time_left <= 0:
            if self.shutdown_timer_id is None:
                self.start_shutdown_countdown()
            self.indicator.set_label("", "")
            seconds = max(0, int((self.countdown_end - now).total_seconds() + 0.999))
            title = f"Выключение через {seconds} секунд. Можно продлить время."
            self.indicator.set_title(title)
            self.time_item.set_label(title)
            self.update_icon(warning=True)
            self.update_menu_state()
            return True

        # Проверка на предупреждение
        warn_seconds = self.warn_minutes * 60
        if time_left <= warn_seconds and not self.warned:
            self.show_warning_notification(int(time_left / 60))
            self.warned = True

        # Вычисляем время для отображения
        minutes_left = int(time_left / 60)
        seconds_left = int(time_left % 60)
        hours = minutes_left // 60
        mins = minutes_left % 60

        if hours > 0:
            time_display = f"{hours}ч {mins}м"
        elif minutes_left > 0:
            time_display = f"{mins}м"
        else:
            # Последняя минута - показываем секунды
            time_display = f"{seconds_left}с"

        # Убираем текст из трея, оставляем только иконку
        self.indicator.set_label("", "")

        # Устанавливаем tooltip с информацией о времени
        shutdown_str = self.shutdown_time.strftime('в %H:%M')
        if self.shutdown_time.date() != now.date():
            shutdown_str = self.shutdown_time.strftime('%d.%m в %H:%M')
        if minutes_left > 0:
            tooltip = f"Выключение {shutdown_str} (осталось {time_display})"
        else:
            tooltip = f"Выключение через {seconds_left} секунд"
        self.indicator.set_title(tooltip)

        # Обновляем пункт меню
        if self.time_item:
            self.time_item.set_label(tooltip)

        # Обновляем иконку в зависимости от оставшегося времени
        if time_left <= warn_seconds:
            self.update_icon(warning=True)  # Красная иконка
        else:
            self.update_icon(warning=False)  # Обычная иконка

        self.update_menu_state()
        return True

    def update_menu_state(self):
        """Обновление состояния пунктов меню (активно/неактивно)"""
        if hasattr(self, 'extend_item'):
            # Продлить время доступно только если выключение включено
            self.extend_item.set_sensitive(self.shutdown_time is not None)
            self.extend_item.set_label(f"Продлить на {self.extend_minutes} мин")

        return True

    def extend_time(self, widget):
        """Продление времени выключения"""
        if not self.shutdown_time:
            logger.warning("Попытка продлить время при отключённом выключении")
            return

        if self.shutdown_time:
            new_shutdown = self.shutdown_time + timedelta(minutes=self.extend_minutes)
            self.close_warning_notification()
            self.cancel_pending_shutdown()
            self.shutdown_time = new_shutdown
            self.warned = False  # Сбрасываем флаг предупреждения
            logger.info(f"Время продлено на {self.extend_minutes} мин. "
                       f"Новое время: {self.shutdown_time.strftime('%H:%M')}")

            notification = Notify.Notification.new(
                "Время продлено",
                f"Выключение перенесено на {self.shutdown_time.strftime('%H:%M')}",
                "dialog-information"
            )
            notification.show()

            self.update_indicator()

    def show_warning_notification(self, minutes_left):
        """Показ предупреждения о скором выключении"""
        logger.info(f"Показ предупреждения: осталось {minutes_left} мин")
        self.close_warning_notification()

        notification = Notify.Notification.new(
            "Скоро выключение ПК",
            f"Компьютер будет выключен через {minutes_left} мин.\n"
            f"Чтобы продлить время, откройте меню в трее.",
            "dialog-warning"
        )
        notification.set_urgency(Notify.Urgency.CRITICAL)
        notification.set_timeout(30000)  # 30 секунд

        if self.interactive:
            notification.add_action("extend", f"Продлить на {self.extend_minutes} мин",
                                   self.notification_extend_callback)
            notification.add_action("ok", "ОК", self.notification_ok_callback)

        # LibNotify disconnects DBus signals when this object is destroyed.
        # Keep it alive after this method returns, until closed or superseded.
        self.warning_notification = notification
        notification.connect('closed', self.warning_notification_closed)
        try:
            notification.show()
        except Exception:
            self.close_warning_notification()
            raise

    def warning_notification_closed(self, notification):
        if getattr(self, 'warning_notification', None) is notification:
            self.warning_notification = None

    def close_warning_notification(self):
        notification = getattr(self, 'warning_notification', None)
        self.warning_notification = None
        if notification is not None:
            try:
                notification.close()
            except Exception:
                logger.exception('Не удалось закрыть предупреждение')

    def notification_ok_callback(self, notification, action, user_data=None):
        if getattr(self, 'warning_notification', None) is notification:
            self.close_warning_notification()

    def show_shutdown_notification(self):
        """Показ уведомления о начале выключения (когда время пришло)"""
        logger.info("Показ финального уведомления о выключении")

        notification = Notify.Notification.new(
            "Выключение ПК",
            "Компьютер выключится через 15 секунд...",
            "system-shutdown"
        )
        notification.set_urgency(Notify.Urgency.CRITICAL)
        notification.set_timeout(15000)  # 15 секунд
        self.final_notification = notification
        notification.show()

    def cancel_pending_shutdown(self):
        """Отменяет финальный таймер при продлении или смене расписания."""
        if getattr(self, 'shutdown_timer_id', None) is not None:
            GLib.source_remove(self.shutdown_timer_id)
        self.shutdown_timer_id = None
        self.pending_shutdown = None
        if getattr(self, 'final_notification', None) is not None:
            try:
                self.final_notification.close()
            except Exception:
                logger.exception('Не удалось закрыть финальное уведомление')
            self.final_notification = None

    def start_shutdown_countdown(self):
        self.close_warning_notification()
        deadline = self.shutdown_time
        self.pending_shutdown = deadline
        self.countdown_end = datetime.now() + timedelta(seconds=15)
        self.shutdown_timer_id = GLib.timeout_add_seconds(
            15, self.finish_shutdown_countdown, deadline)
        try:
            self.show_shutdown_notification()
        except Exception:
            logger.exception('Не удалось показать финальное уведомление')

    def finish_shutdown_countdown(self, deadline):
        # Защита от устаревшего callback и изменения срока во время ожидания.
        if self.pending_shutdown != deadline:
            return False
        self.shutdown_timer_id = None
        self.pending_shutdown = None
        if self.shutdown_time != deadline or datetime.now() < deadline:
            self.cancel_pending_shutdown()
            return False
        succeeded = self.perform_shutdown()
        # Не повторяем неудачную попытку каждую секунду. Следующий цикл берёт
        # базовое расписание, поэтому сегодняшнее продление на него не переносится.
        self.shutdown_time = self.parse_shutdown_time(self.config['shutdown_time'])
        self.warned = False
        self.cancel_pending_shutdown()
        if not succeeded:
            self.show_error_notification(
                'Не удалось выключить ПК',
                f'Проверьте права и журнал. Следующая попытка по расписанию: '
                f'{self.shutdown_time:%d.%m %H:%M}')
        self.update_indicator()
        return False

    def notification_extend_callback(self, notification, action, user_data=None):
        """Callback для кнопки 'Продлить' в уведомлении"""
        if getattr(self, 'warning_notification', None) is not notification:
            return
        logger.info('Нажата кнопка продления в уведомлении')
        self.extend_time(None)

    def show_error_notification(self, title, message):
        """Показ уведомления об ошибке"""
        try:
            notification = Notify.Notification.new(title, message, "dialog-error")
            notification.show()
        except Exception:
            logger.exception('Не удалось показать сообщение об ошибке: %s', message)

    def perform_shutdown(self):
        """Выполнение выключения ПК через systemd-logind"""
        logger.info("Выполняется выключение ПК...")

        try:
            bus = dbus.SystemBus()
            login1 = bus.get_object('org.freedesktop.login1',
                                   '/org/freedesktop/login1')
            login1_interface = dbus.Interface(login1,
                                             'org.freedesktop.login1.Manager')
            # PowerOff(interactive: bool)
            login1_interface.PowerOff(self.interactive)
            return True
        except Exception as e:
            logger.error(f"Ошибка выключения через DBus: {e}")
            # Fallback на systemctl
            import subprocess
            try:
                subprocess.run(['systemctl', 'poweroff'], check=True)
                return True
            except (subprocess.CalledProcessError, OSError) as e2:
                logger.error(f"Ошибка systemctl poweroff: {e2}")
                return False

    def manual_reload_config(self, widget):
        """Ручная перезагрузка конфига (через меню)"""
        logger.info("Ручная перезагрузка конфигурации")
        old_reload_minutes = self.reload_minutes

        if not self.load_config():
            return False
        self.update_indicator()

        # Если интервал изменился, пересоздаём таймер автоперезагрузки
        if self.reload_minutes != old_reload_minutes:
            logger.info(f"Интервал перезагрузки изменился: {old_reload_minutes} -> {self.reload_minutes} мин")
            # Удаляем старый таймер
            if hasattr(self, 'reload_timer_id') and self.reload_timer_id:
                GLib.source_remove(self.reload_timer_id)
            # Создаём новый таймер с новым интервалом
            self.reload_timer_id = GLib.timeout_add_seconds(self.reload_minutes * 60, self.reload_config_timer)

        # Показываем уведомление
        notification = Notify.Notification.new(
            "Конфигурация перезагружена",
            "Настройки успешно обновлены",
            "dialog-information"
        )
        notification.show()

    def reload_config_timer(self):
        """Таймер перезагрузки конфигурации"""
        logger.info("Перезагрузка конфигурации по таймеру")
        old_reload_minutes = self.reload_minutes

        if not self.load_config():
            return True
        self.update_indicator()

        # Если интервал изменился, пересоздаём таймер
        if self.reload_minutes != old_reload_minutes:
            logger.info(f"Интервал перезагрузки изменился: {old_reload_minutes} -> {self.reload_minutes} мин")
            # Удаляем старый таймер
            if hasattr(self, 'reload_timer_id') and self.reload_timer_id:
                GLib.source_remove(self.reload_timer_id)
            # Создаём новый таймер с новым интервалом
            self.reload_timer_id = GLib.timeout_add_seconds(self.reload_minutes * 60, self.reload_config_timer)
            return False  # Останавливаем старый таймер

        return True  # Продолжаем работу таймера

    def quit(self, widget):
        """Выход из приложения"""
        logger.info("Выход из демона по запросу пользователя")
        Notify.uninit()
        Gtk.main_quit()


def main():
    """Точка входа"""
    daemon = PoweroffDaemon()
    Gtk.main()


if __name__ == '__main__':
    main()
