# بسم الله الرحمان الرحيم
"""
All the QThread elements we use for asynchronous works
"""
import math
import struct
import pyaudio
import wave
import os

from symspellpy import SymSpell

from PyQt5.QtCore import QThread, pyqtSignal

from tools import G


class Dictionnary(QThread):
    """
    QThread to load the dictionnary in multithreading
    """
    finished = pyqtSignal()
    dict_path = G.rsc_path("dict.txt")
    sympell = SymSpell(max_dictionary_edit_distance=2, prefix_length=5)

    def run(self):
        # Loading dictionnary for orthographic correction
        self.sympell.load_dictionary(self.dict_path, term_index=0, count_index=1, encoding="utf8", separator="\t")
        self.finished.emit()


class AudioWorker(QThread):
    """
    QThread for asynchronous audio recording
    """
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    audio_pike = pyqtSignal(int)
    filename = ''
    running = False

    @staticmethod
    def rms(data):
        """
        Return the level of db from data, found the function online
        :param data: audio data
        """
        count = len(data) / 2
        shorts = struct.unpack(f'{count}h', data)
        sum_squares = 0.0

        for sample in shorts:
            n = sample * (1.0 / 32768)
            sum_squares += n * n

        return math.sqrt(sum_squares / count)

    def run(self):
        """
        Main process of the thread will be run in multithreading
        """
        chunk = 1024
        sample_format = pyaudio.paInt16
        channels = 2
        sample_rate = 16000

        # we store the file in the Music folder of the user
        # TODO: need to be specified in settings
        filename = G.user_path(f"Music/.typer_records/{self.filename}.wav")
        if not os.path.isdir(os.path.dirname(filename)):
            os.mkdir(os.path.dirname(filename))

        # specifying the record's settings
        pa = pyaudio.PyAudio()
        stream = pa.open(format=sample_format, channels=channels, rate=sample_rate, input=True,
                         frames_per_buffer=chunk, input_device_index=2)

        # starts record until user ask to stop
        self.running = True

        i, frames = 0, []
        while self.running:
            data = stream.read(chunk)

            # arbitrary determining the volume for visual output
            volume = int(math.log(abs(self.rms(data)) * 50) + 2) * 20

            # emitting the signals
            self.audio_pike.emit(volume)
            self.progress.emit(int(float(i) * 1024 // 16000))

            # storing data
            frames.append(data)
            i += 1

        # now we stop the recording and save file
        stream.stop_stream()
        stream.close()
        pa.terminate()

        # saving file
        sf = wave.open(filename, 'wb')
        sf.setnchannels(channels)
        sf.setsampwidth(pa.get_sample_size(sample_format))
        sf.setframerate(sample_rate)
        sf.writeframes(b''.join(frames))
        sf.close()

        # now we signal that the recording's done
        self.finished.emit()

    def stop(self):
        self.running = False
