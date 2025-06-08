import sys
import speech_recognition as sr
import pyttsx3
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QMessageBox, QPushButton, QHBoxLayout, QProgressBar, QTextEdit, QInputDialog
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
import pyaudio
import pyautogui
import keyboard
import mouse
import os
import subprocess
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import traceback
import time
import json
CHUNK = 1024  
FORMAT = pyaudio.paFloat32  
CHANNELS = 1  
RATE = 44100  
@dataclass
class AudioConfig:
    CHUNK: int = 1024
    FORMAT: int = pyaudio.paFloat32
    CHANNELS: int = 1
    RATE: int = 44100
def log_command(command: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Распознана команда: {command}")
def get_available_microphones() -> List[tuple]:
    p = pyaudio.PyAudio()
    microphones = []
    try:
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                if (device_info.get('maxInputChannels') > 0 and 
                    device_info.get('name') and 
                    'fifine' in device_info.get('name').lower()):
                    name = device_info.get('name', '').strip()
                    microphones.append((i, name))
                    print(f"Найден микрофон fifine: {name} (индекс: {i})")
            except Exception as e:
                print(f"Ошибка при получении информации об устройстве {i}: {e}")
    finally:
        p.terminate()
    return microphones
class AudioVisualizer(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)
        self.audio_data = np.zeros(100)
        self.config = AudioConfig()
        try:
            self.setup_audio()
        except Exception as e:
            print(f"Ошибка инициализации аудио: {e}")
            QMessageBox.critical(None, "Ошибка", f"Не удалось инициализировать аудио: {e}")
    def setup_audio(self) -> None:
        try:
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(
                format=self.config.FORMAT,
                channels=self.config.CHANNELS,
                rate=self.config.RATE,
                input=True,
                frames_per_buffer=self.config.CHUNK
            )
        except Exception as e:
            raise Exception(f"Ошибка при настройке аудио: {e}")
    def update_audio(self) -> None:
        try:
            data = np.frombuffer(self.stream.read(self.config.CHUNK), dtype=np.float32)
            self.audio_data = np.roll(self.audio_data, -1)
            self.audio_data[-1] = np.abs(data).mean()
            self.update()
        except Exception as e:
            print(f"Ошибка обновления аудио: {e}")
    def paintEvent(self, event) -> None:
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            width = self.width()
            height = self.height()
            painter.setPen(QColor(0, 255, 0))
            for i in range(len(self.audio_data) - 1):
                x1 = i * width / len(self.audio_data)
                y1 = height/2 + self.audio_data[i] * height/2
                x2 = (i + 1) * width / len(self.audio_data)
                y2 = height/2 + self.audio_data[i + 1] * height/2
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        except Exception as e:
            print(f"Ошибка отрисовки: {e}")
class VoiceListener(QThread):
    command_recognized = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    def __init__(self, device_index: int):
        super().__init__()
        self.recognizer = sr.Recognizer()
        self.device_index = device_index
        self.running = True
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 0.5
        self.recognizer.operation_timeout = 15
        self.is_listening = False
        self.microphone = None
    def run(self):
        try:
            with sr.Microphone(device_index=self.device_index) as source:
                print("Микрофон готов к работе")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                while self.running:
                    try:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                        try:
                            text = self.recognizer.recognize_google(audio, language='ru-RU')
                            print(f"Распознано: {text}")
                            self.command_recognized.emit(text)
                            continue
                        except sr.UnknownValueError:
                            pass
                        try:
                            text = self.recognizer.recognize_google(audio, language='en-US')
                            print(f"Распознано (EN): {text}")
                            self.command_recognized.emit(text)
                        except sr.UnknownValueError:
                            pass
                    except sr.WaitTimeoutError:
                        continue
                    except sr.RequestError as e:
                        print(f"Ошибка сервиса распознавания: {e}")
        except Exception as e:
            print(f"Ошибка микрофона: {e}")
            self.error_occurred.emit(str(e))
    def stop(self):
        self.running = False
class JarvisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Джарвис")
        self.setMinimumSize(500, 400)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.custom_commands = {}
        self.commands_file = 'custom_commands.json'
        self.load_custom_commands()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.setStyleSheet("""
            QMainWindow {
                background-color: 
                color: 
            }
            QLabel {
                color: 
            }
            QTextEdit {
                background-color: 
                color: 
                border: 1px solid 
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: 
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: 
            }
            QPushButton:pressed {
                background-color: 
            }
            QProgressBar {
                border: 1px solid 
                border-radius: 3px;
                background-color: 
                color: white;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: 
            }
        """)
        self.info_label = QLabel("Инициализация...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        commands_label = QLabel("""
🔍 Доступные команды:
🔵 "Джарвис" — Активация помощника
📝 "Введи текст [текст]" — Ввод текста в строку
❌ "Закрой окно" — Закрытие активного окна
🚀 "Запусти [программа]" — Запуск указанной программы
📂 "Открой [папка]" — Открытие указанной папки
🔴 "Выключи компьютер" — Выключение через 60 секунд
🔄 "Перезагрузи компьютер" — Перезагрузка через 60 секунд
⏳ "Отмени выключение" — Отмена выключения или перезагрузки
➕ "Добавь команду" — Создание новой команды
📜 "Покажи команды" — Отображение пользовательских команд
""")
        commands_label.setStyleSheet("""
            background-color: 
            padding: 15px;
            border-radius: 5px;
            margin: 5px;
            color: 
            font-size: 12px;
        """)
        layout.addWidget(commands_label)
        self.volume_bar = QProgressBar()
        self.volume_bar.setMinimum(0)
        self.volume_bar.setMaximum(100)
        self.volume_bar.setTextVisible(True)
        self.volume_bar.setFormat("Уровень: %p%")
        layout.addWidget(self.volume_bar)
        self.calibrate_button = QPushButton("Калибровка (5 сек)")
        self.calibrate_button.clicked.connect(self.start_calibration)
        layout.addWidget(self.calibrate_button)
        self.calibration_label = QLabel("Калибровка не выполнена")
        self.calibration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.calibration_label)
        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setMinimumHeight(100)
        layout.addWidget(self.text_output)
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.max_volume = 1.0
        self.is_calibrating = False
        self.calibration_start_time = 0
        self.calibration_values = []
        self.is_listening = False
        self.volume_timer = QTimer()
        self.volume_timer.timeout.connect(self.update_volume)
        self.initialize_microphone()
    def initialize_microphone(self):
        fifine_index = None
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if 'fifine' in dev_info.get('name', '').lower():
                fifine_index = i
                try:
                    mic_name = "Микрофон Fifine"
                    self.info_label.setText(mic_name)
                except Exception as e:
                    self.info_label.setText(f"Микрофон Fifine (индекс: {i})")
                break
        if fifine_index is None:
            self.info_label.setText("Микрофон fifine не найден!")
            return
        try:
            self.stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=fifine_index,
                frames_per_buffer=CHUNK
            )
            self.volume_timer.start(20)
            self.voice_listener = VoiceListener(fifine_index)
            self.voice_listener.command_recognized.connect(self.handle_command)
            self.voice_listener.error_occurred.connect(self.handle_error)
            self.voice_listener.start()
            print("Микрофон инициализирован и готов к работе")
        except Exception as e:
            self.info_label.setText(f"Ошибка: {str(e)}")
    def handle_command(self, text):
        if not self.is_listening:
            if "джарвис" in text.lower():
                self.text_output.clear()  
                self.text_output.append("🎤 Распознано: " + text)
                self.text_output.append("✓ Активация: Джарвис")
                self.text_output.append("👂 Слушаю...")
                self.is_listening = True
                print("Джарвис активирован")
        else:
            self.text_output.append("\n🎤 Распознано: " + text)
            self.process_command(text)
            self.is_listening = False
            self.text_output.append("\n⏳ Ожидаю активации...")
            print("Команда обработана")
    def handle_error(self, error):
        print(f"Ошибка распознавания: {error}")
        self.text_output.append(f"\nОшибка: {error}")
    def start_calibration(self):
        self.is_calibrating = True
        self.calibration_start_time = time.time()
        self.calibration_values = []
        self.calibrate_button.setEnabled(False)
        self.calibration_label.setText("Идет калибровка... Говорите в микрофон")
    def update_volume(self):
        if not self.stream:
            return
        try:
            data = np.frombuffer(self.stream.read(CHUNK, exception_on_overflow=False), dtype=np.float32)
            volume = np.abs(data).mean()
            if self.is_calibrating:
                self.calibration_values.append(volume)
                elapsed = time.time() - self.calibration_start_time
                if elapsed >= 5:
                    self.is_calibrating = False
                    self.max_volume = max(self.calibration_values)
                    self.calibrate_button.setEnabled(True)
                    status_msg = f"Калибровка завершена. Макс. уровень: {self.max_volume:.4f}"
                    print(f"\n{status_msg}")
                    self.calibration_label.setText(status_msg)
            normalized_volume = min(100, int((volume / self.max_volume) * 100))
            self.volume_bar.setValue(normalized_volume)
        except Exception as e:
            if "Input overflowed" not in str(e):
                error_msg = f"Ошибка чтения: {str(e)}"
                print(error_msg)
                self.info_label.setText(error_msg)
    def load_custom_commands(self):
        try:
            if os.path.exists(self.commands_file):
                with open(self.commands_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.custom_commands = {k: v for k, v in data.items() if not k.startswith('//')}
                print("Загружены пользовательские команды:")
                for command, action in self.custom_commands.items():
                    print(f"• {command} -> {action}")
        except Exception as e:
            print(f"Ошибка загрузки пользовательских команд: {e}")
            self.create_commands_template()
    def create_commands_template(self):
        template = {
            "// Это файл с пользовательскими командами для Джарвис": "",
            "// Формат команд:": "",
            "// 'команда': 'действие'": "",
            "// Примеры:": "",
            "// Для открытия сайта:": "",
            "открой youtube": "https://youtube.com",
            "// Для запуска программы:": "",
            "открой блокнот": "notepad.exe",
            "// Для открытия папки:": "",
            "открой документы": "C:\\Users\\Public\\Documents",
            "// Добавьте свои команды ниже:": ""
        }
        try:
            with open(self.commands_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, ensure_ascii=False, indent=4)
            print("Создан шаблон файла команд")
        except Exception as e:
            print(f"Ошибка создания шаблона команд: {e}")
    def save_custom_commands(self):
        try:
            current_data = {}
            if os.path.exists(self.commands_file):
                with open(self.commands_file, 'r', encoding='utf-8') as f:
                    current_data = json.load(f)
            for command, action in self.custom_commands.items():
                current_data[command] = action
            with open(self.commands_file, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=4)
            print("Пользовательские команды сохранены")
        except Exception as e:
            print(f"Ошибка сохранения пользовательских команд: {e}")
    def add_custom_command(self, command_name):
        try:
            action, ok = QInputDialog.getText(
                self,
                "Новая команда",
                f"Введите действие для команды '{command_name}':\n\n"
                "Примеры:\n"
                "• https://youtube.com - для открытия сайта\n"
                "• notepad.exe - для запуска программы\n"
                "• C:\\Путь\\К\\Папке - для открытия папки"
            )
            if ok and action:
                self.custom_commands[command_name] = action
                self.save_custom_commands()
                self.text_output.append(f"✓ Добавлена команда: '{command_name}' -> {action}")
                print(f"Добавлена команда: {command_name} -> {action}")
        except Exception as e:
            error = f"Ошибка добавления команды: {e}"
            self.text_output.append(f"❌ {error}")
            print(error)
    def show_custom_commands(self):
        if not self.custom_commands:
            self.text_output.append("ℹ️ Пользовательских команд пока нет")
            return
        self.text_output.append("\n📋 Пользовательские команды:")
        for command, action in self.custom_commands.items():
            self.text_output.append(f"• {command} -> {action}")
    def process_command(self, command):
        try:
            command = command.lower()
            print(f"Обработка команды: {command}")
            add_command_variants = [
                "добавь команду", "добавить команду", "создай команду",
                "создать команду", "новая команда", "сделай команду"
            ]
            if any(x in command for x in add_command_variants):
                command_name = command
                for variant in add_command_variants:
                    command_name = command_name.replace(variant, "").strip()
                if command_name:
                    self.add_custom_command(command_name)
                else:
                    self.text_output.append("❌ Укажите имя команды")
                    print("Не указано имя команды")
            elif any(x in command for x in [
                "покажи команды", "показать команды", "список команд",
                "какие команды", "доступные команды", "что умеешь"
            ]):
                self.show_custom_commands()
            elif command in self.custom_commands:
                action = self.custom_commands[command]
                try:
                    if action.startswith(('http://', 'https://')):
                        os.startfile(action)
                        self.text_output.append(f"✓ Открываю: {action}")
                    else:
                        subprocess.Popen(action, shell=True)
                        self.text_output.append(f"✓ Выполняю: {action}")
                except Exception as e:
                    error = f"Ошибка выполнения команды: {e}"
                    self.text_output.append(f"❌ {error}")
                    print(error)
            elif any(x in command for x in [
                "введи текст", "напиши", "набери", "напечатай",
                "введи", "написать", "печатай"
            ]):
                text_to_type = command
                for variant in ["введи текст", "напиши", "набери", 
                              "напечатай", "введи", "написать", "печатай"]:
                    text_to_type = text_to_type.replace(variant, "").strip()
                if text_to_type:
                    self.text_output.append(f"✓ Ввожу текст через 2 секунды: '{text_to_type}'")
                    QTimer.singleShot(2000, lambda: self.type_text(text_to_type))
            elif any(x in command for x in [
                "закрой окно", "закрыть окно", "закрой вкладку",
                "закрыть вкладку", "закрой программу", "выход"
            ]):
                keyboard.send("alt+f4")
                self.text_output.append("✓ Закрытие окна")
                print("Выполнено: закрытие окна")
            elif any(x in command for x in [
                "запусти", "запустить", "открой программу",
                "включи", "старт", "загрузи"
            ]):
                app_name = command
                for variant in ["запусти", "запустить", "открой программу",
                              "включи", "старт", "загрузи"]:
                    app_name = app_name.replace(variant, "").strip()
                try:
                    if os.path.exists(app_name):
                        subprocess.Popen(app_name)
                        self.text_output.append(f"✓ Запущено: '{app_name}'")
                    else:
                        subprocess.Popen(f"start {app_name}", shell=True)
                        self.text_output.append(f"✓ Запущено: '{app_name}'")
                    print(f"Запущено: {app_name}")
                except Exception as e:
                    error = f"Ошибка запуска: {e}"
                    self.text_output.append(f"❌ {error}")
                    print(error)
            elif any(x in command for x in [
                "открой", "открыть", "покажи папку",
                "открой папку", "перейти в"
            ]):
                folder_name = command
                for variant in ["открой", "открыть", "покажи папку",
                              "открой папку", "перейти в"]:
                    folder_name = folder_name.replace(variant, "").strip()
                try:
                    if os.path.exists(folder_name):
                        os.startfile(folder_name)
                        self.text_output.append(f"✓ Открыто: '{folder_name}'")
                        print(f"Открыто: {folder_name}")
                    else:
                        error = f"Папка '{folder_name}' не найдена"
                        self.text_output.append(f"❌ {error}")
                        print(error)
                except Exception as e:
                    error = f"Ошибка открытия: {e}"
                    self.text_output.append(f"❌ {error}")
                    print(error)
            elif any(x in command for x in [
                "выключи компьютер", "выключить компьютер",
                "выключи систему", "выключение", "shutdown",
                "выключи пк", "выруби компьютер"
            ]):
                os.system("shutdown /s /t 60")
                msg = "Выключение через 60 секунд"
                self.text_output.append(f"✓ {msg}")
                print(msg)
            elif any(x in command for x in [
                "перезагрузи компьютер", "перезагрузить компьютер",
                "перезагрузи систему", "рестарт", "restart",
                "перезагрузи пк", "перезапусти компьютер"
            ]):
                os.system("shutdown /r /t 60")
                msg = "Перезагрузка через 60 секунд"
                self.text_output.append(f"✓ {msg}")
                print(msg)
            elif any(x in command for x in [
                "отмени выключение", "отменить выключение",
                "отмена выключения", "отмени перезагрузку",
                "стоп выключение", "остановить выключение"
            ]):
                os.system("shutdown /a")
                msg = "Выключение/перезагрузка отменены"
                self.text_output.append(f"✓ {msg}")
                print(msg)
            elif any(x in command for x in [
                "найди в интернете", "найти в интернете",
                "поищи в интернете", "поиск в интернете",
                "найди в гугле", "поищи в гугле",
                "найди в google", "поищи в google"
            ]):
                search_query = command
                for variant in ["найди в интернете", "найти в интернете",
                              "поищи в интернете", "поиск в интернете",
                              "найди в гугле", "поищи в гугле",
                              "найди в google", "поищи в google"]:
                    search_query = search_query.replace(variant, "").strip()
                if search_query:
                    search_url = f"https://www.google.com/search?q={search_query}"
                    os.startfile(search_url)
                    self.text_output.append(f"✓ Открываю поиск: '{search_query}'")
                    print(f"Открыт поиск: {search_query}")
                else:
                    self.text_output.append("❌ Укажите, что нужно найти")
                    print("Не указан поисковый запрос")
            else:
                self.text_output.append("❌ Неизвестная команда")
                print("Неизвестная команда")
        except Exception as e:
            error = f"Ошибка обработки команды: {e}"
            self.text_output.append(f"❌ {error}")
            print(error)
        self.text_output.verticalScrollBar().setValue(
            self.text_output.verticalScrollBar().maximum()
        )
    def type_text(self, text):
        try:
            keyboard.write(text)
            print(f"Введен текст: {text}")
        except Exception as e:
            error = f"Ошибка ввода текста: {e}"
            self.text_output.append(f"❌ {error}")
            print(error)
    def closeEvent(self, event):
        if hasattr(self, 'voice_listener'):
            self.voice_listener.stop()
            self.voice_listener.wait()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        event.accept()
def main() -> None:
    try:
        app = QApplication(sys.argv)
        window = JarvisWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        traceback.print_exc()
        QMessageBox.critical(None, "Критическая ошибка", f"Не удалось запустить приложение: {e}")
if __name__ == '__main__':
    main() 