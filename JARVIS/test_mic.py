import sys
import pyaudio
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar
from PyQt6.QtCore import QTimer, Qt
import time
CHUNK = 1024  
FORMAT = pyaudio.paFloat32  
CHANNELS = 1  
RATE = 44100  
class MicrophoneWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Тест микрофона")
        self.setMinimumSize(400, 200)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.info_label = QLabel("Инициализация...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
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
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.max_volume = 1.0  
        self.is_calibrating = False
        self.calibration_start_time = 0
        self.calibration_values = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_volume)
        self.initialize_microphone()
    def initialize_microphone(self):
        fifine_index = None
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if 'fifine' in dev_info.get('name', '').lower():
                fifine_index = i
                try:
                    mic_name = dev_info['name']
                    if isinstance(mic_name, bytes):
                        mic_name = mic_name.decode('utf-8')
                    mic_name = ' '.join(mic_name.split())
                    self.info_label.setText(f"Микрофон: {mic_name}")
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
            self.timer.start(50)  
        except Exception as e:
            self.info_label.setText(f"Ошибка: {str(e)}")
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
            data = np.frombuffer(self.stream.read(CHUNK), dtype=np.float32)
            volume = np.abs(data).mean()
            if self.is_calibrating:
                self.calibration_values.append(volume)
                elapsed = time.time() - self.calibration_start_time
                if elapsed >= 5:  
                    self.is_calibrating = False
                    self.max_volume = max(self.calibration_values)
                    self.calibrate_button.setEnabled(True)
                    self.calibration_label.setText(f"Калибровка завершена. Макс. уровень: {self.max_volume:.4f}")
            normalized_volume = min(100, int((volume / self.max_volume) * 100))
            self.volume_bar.setValue(normalized_volume)
        except Exception as e:
            self.info_label.setText(f"Ошибка чтения: {str(e)}")
    def closeEvent(self, event):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        event.accept()
def main():
    app = QApplication(sys.argv)
    window = MicrophoneWindow()
    window.show()
    sys.exit(app.exec())
if __name__ == '__main__':
    main() 