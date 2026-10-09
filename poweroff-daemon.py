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
        # Обычно раз в минуту, но переключаемся на каждую секунду в последнюю минуту
        self.update_timer_id = GLib.timeout_add_seconds(60, self.update_indicator)

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

    def load_config(self):
        """Загрузка конфигурации из /etc/poweroff.time"""
        if not os.path.exists(self.CONFIG_PATH):
            logger.error(f"Конфигурационный файл {self.CONFIG_PATH} не найден")
            self.show_error_notification("Конфиг не найден",
                                        f"Файл {self.CONFIG_PATH} отсутствует")
            return False

        try:
            config = configparser.ConfigParser()
            config.read(self.CONFIG_PATH, encoding='utf-8')

            # Загружаем дефолтные значения
            defaults = config['default'] if 'default' in config else {}

            # Проверяем что в default нет 'none'
            default_shutdown_time = defaults.get('shutdown_time', '18:00')
            if default_shutdown_time.lower() == 'none':
                logger.error("shutdown_time = none не допускается в секции [default]")
                self.show_error_notification("Ошибка конфига",
                                            "shutdown_time = none допускается только в пользовательских секциях")
                return False

            # Ищем пользовательскую секцию [user:username]
            user_section = f'user:{self.username}'
            user_config = config[user_section] if user_section in config else {}

            # Получаем параметры с fallback на default
            shutdown_time_str = user_config.get('shutdown_time',
                                               defaults.get('shutdown_time', '18:00'))
            self.extend_minutes = int(user_config.get('extend_minutes',
                                                     defaults.get('extend_minutes', 30)))
            self.warn_minutes = int(user_config.get('warn_minutes',
                                                   defaults.get('warn_minutes', 10)))
            self.reload_minutes = int(user_config.get('reload_minutes',
                                                     defaults.get('reload_minutes', 15)))
            self.interactive = user_config.get('interactive',
                                              defaults.get('interactive', 'true')).lower() == 'true'

            # Парсим дни недели
            days_str = user_config.get('days', defaults.get('days', '1,2,3,4,5,6,7'))
            self.active_days = self.parse_days(days_str)

            # Проверяем на 'none' (отключение выключения для пользователя)
            if shutdown_time_str.lower() == 'none':
                self.shutdown_time = None
                logger.info(f"Выключение отключено для пользователя {self.username}")
            else:
                # Парсим время выключения
                self.shutdown_time = self.parse_shutdown_time(shutdown_time_str)

            self.warned = False  # Сбрасываем флаг предупреждения при перезагрузке

            logger.info(f"Конфигурация загружена: shutdown_time={self.shutdown_time}, "
                       f"extend={self.extend_minutes}m, warn={self.warn_minutes}m, "
                       f"reload={self.reload_minutes}m, interactive={self.interactive}, "
                       f"active_days={self.active_days}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            self.show_error_notification("Ошибка конфига", str(e))
            return False

    def parse_days(self, days_str):
        """Парсинг списка дней недели из строки '1,2,3,4,5'"""
        try:
            days = [int(d.strip()) for d in days_str.split(',')]
            # Проверяем что все значения в диапазоне 1-7
            valid_days = [d for d in days if 1 <= d <= 7]
            if not valid_days:
                logger.warning(f"Неверный формат дней '{days_str}', используются все дни")
                return [1, 2, 3, 4, 5, 6, 7]
            logger.info(f"Активные дни недели: {valid_days}")
            return sorted(valid_days)
        except Exception as e:
            logger.error(f"Ошибка парсинга дней '{days_str}': {e}")
            return [1, 2, 3, 4, 5, 6, 7]

    def find_next_active_shutdown(self):
        """Находит следующую дату/время выключения с учётом активных дней"""
        now = datetime.now()
        # Берём время из текущего shutdown_time
        shutdown_time = self.shutdown_time.time()

        # Начинаем с завтрашнего дня
        next_dt = datetime.combine(now.date() + timedelta(days=1), shutdown_time)

        # Ищем следующий активный день (максимум 7 дней)
        for _ in range(7):
            if next_dt.isoweekday() in self.active_days:
                logger.info(f"Следующее выключение: {next_dt}")
                return next_dt
            next_dt += timedelta(days=1)

        # Если не нашли (все дни отключены), возвращаем через неделю
        return datetime.combine(now.date() + timedelta(days=7), shutdown_time)

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

    def parse_shutdown_time(self, time_str):
        """Парсинг времени выключения из строки HH:MM с учётом активных дней недели"""
        try:
            t = datetime.strptime(time_str.strip(), '%H:%M').time()
            now = datetime.now()
            shutdown_dt = datetime.combine(now.date(), t)

            # Если время уже прошло сегодня, берём завтра
            # Используем < вместо <= чтобы текущая минута считалась "не прошедшей"
            if shutdown_dt < now:
                shutdown_dt += timedelta(days=1)
                logger.info(f"Время {time_str} уже прошло сегодня, ищем следующий активный день")

            # Находим следующий активный день недели
            # weekday() возвращает 0=Monday, 6=Sunday, нам нужно 1=Monday, 7=Sunday
            max_attempts = 7  # Максимум 7 дней проверяем
            for _ in range(max_attempts):
                current_weekday = shutdown_dt.isoweekday()  # 1=Monday, 7=Sunday
                if current_weekday in self.active_days:
                    logger.info(f"Время выключения: {shutdown_dt} (день недели {current_weekday})")
                    return shutdown_dt
                else:
                    logger.info(f"День {current_weekday} не активен, пропускаем")
                    shutdown_dt += timedelta(days=1)

            # Если не нашли активный день (все дни отключены), возвращаем текущее время
            logger.warning("Не найден активный день недели, используется текущая дата")
            return datetime.combine(now.date(), t)

        except ValueError as e:
            logger.error(f"Неверный формат времени '{time_str}': {e}")
            # Дефолтное время - через 2 часа
            return datetime.now() + timedelta(hours=2)

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
        current_weekday = now.isoweekday()  # 1=Monday, 7=Sunday

        # Проверяем активен ли сегодняшний день
        if current_weekday not in self.active_days:
            # Сегодня не рабочий день, пересчитываем время на следующий активный день
            logger.info(f"Сегодня день {current_weekday} не активен, пересчитываем время выключения")
            # Сбрасываем флаг быстрого режима
            if hasattr(self, '_fast_mode'):
                delattr(self, '_fast_mode')
            # Пересчитываем shutdown_time на следующий активный день
            self.shutdown_time = self.find_next_active_shutdown()
            self.warned = False

            # Показываем в трее что сегодня выключение не планируется
            self.indicator.set_label("", "")
            next_day_name = self.get_weekday_name(self.shutdown_time.isoweekday())
            shutdown_str = self.shutdown_time.strftime('%H:%M')
            tooltip = f"Сегодня неактивный день. След. выключение: {next_day_name} в {shutdown_str}"
            self.indicator.set_title(tooltip)
            if self.time_item:
                self.time_item.set_label(f"След. выключение: {next_day_name} в {shutdown_str}")
            self.update_icon(warning=False)  # Обычная иконка
            self.update_menu_state()
            return True

        time_left = (self.shutdown_time - now).total_seconds()

        # Проверка на выключение
        if time_left <= 0:
            logger.info("Время выключения наступило")
            # Показываем финальное уведомление
            self.show_shutdown_notification()
            # Выполняем выключение
            self.perform_shutdown()
            return False

        # Проверка на предупреждение
        warn_seconds = self.warn_minutes * 60
        if time_left <= warn_seconds and not self.warned:
            self.show_warning_notification(int(time_left / 60))
            self.warned = True

        # Переключаемся на обновление каждую секунду в последнюю минуту
        if time_left <= 60 and not hasattr(self, '_fast_mode'):
            logger.info("Переключение на быстрое обновление (каждую секунду)")
            self._fast_mode = True
            # Удаляем старый таймер (минутный)
            if hasattr(self, 'update_timer_id') and self.update_timer_id:
                GLib.source_remove(self.update_timer_id)
            # Создаём новый таймер (секундный)
            self.update_timer_id = GLib.timeout_add_seconds(1, self.update_indicator)

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
        shutdown_str = self.shutdown_time.strftime('%H:%M')
        if minutes_left > 0:
            tooltip = f"Выключение в {shutdown_str} (осталось {time_display})"
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

        return True

    def extend_time(self, widget):
        """Продление времени выключения"""
        if not self.shutdown_time:
            logger.warning("Попытка продлить время при отключённом выключении")
            return

        if self.shutdown_time:
            self.shutdown_time += timedelta(minutes=self.extend_minutes)
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
            notification.add_action("ok", "ОК", lambda n, a: None)

        notification.show()

    def show_shutdown_notification(self):
        """Показ уведомления о начале выключения (когда время пришло)"""
        logger.info("Показ финального уведомления о выключении")

        notification = Notify.Notification.new(
            "Выключение ПК",
            "Компьютер выключается через 15 секунд...",
            "system-shutdown"
        )
        notification.set_urgency(Notify.Urgency.CRITICAL)
        notification.set_timeout(15000)  # 15 секунд
        notification.show()

        # Даём время показать уведомление перед выключением
        import time
        time.sleep(15)

    def notification_extend_callback(self, notification, action):
        """Callback для кнопки 'Продлить' в уведомлении"""
        self.extend_time(None)

    def show_error_notification(self, title, message):
        """Показ уведомления об ошибке"""
        notification = Notify.Notification.new(title, message, "dialog-error")
        notification.show()

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
        except Exception as e:
            logger.error(f"Ошибка выключения через DBus: {e}")
            # Fallback на systemctl
            import subprocess
            try:
                subprocess.run(['systemctl', 'poweroff'], check=True)
            except subprocess.CalledProcessError as e2:
                logger.error(f"Ошибка systemctl poweroff: {e2}")

    def manual_reload_config(self, widget):
        """Ручная перезагрузка конфига (через меню)"""
        logger.info("Ручная перезагрузка конфигурации")
        old_reload_minutes = self.reload_minutes

        self.load_config()
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

        self.load_config()
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
