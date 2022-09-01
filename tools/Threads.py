# بسم الله الرحمان الرحيم
"""
All the QThread elements we use for asynchronous works
"""
import pyaudio
import wave
import os

from symspellpy import SymSpell

from PyQt5.QtCore import QThread, pyqtSignal

from tools import G, S


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

    def run(self):
        """
        Main process of the thread will be run in multithreading
        """
        chunk = 1024
        sample_format = pyaudio.paInt16
        channels = G.audio_input_devices[S.GLOBAL.audio_input_device]['channels']
        index = G.audio_input_devices[S.GLOBAL.audio_input_device]['id']
        sample_rate = S.GLOBAL.audio_sample_rate

        # we store the file in the Music folder of the user
        # TODO: need to be specified in settings

        filename = os.path.join(S.GLOBAL.audio_record_path, f'{self.filename}.wav')

        # specifying the record's settings
        pa = pyaudio.PyAudio()
        stream = pa.open(format=sample_format,
                         channels=channels,
                         rate=sample_rate,
                         input=True,
                         frames_per_buffer=chunk,
                         input_device_index=index)

        # starts record until user ask to stop
        self.running = True

        i, frames = 0, []
        zero = 0
        last_pikes = list(range(10))
        while self.running:
            data = stream.read(chunk)

            volume = max(0, sum(list(data)) - zero)
            if not i:
                zero = volume
                volume = 0

            last_pikes.insert(0, volume)
            last_pikes = last_pikes[:9]
            mn = min(last_pikes)
            mx = max(last_pikes) - mn
            volume -= mn

            try:
                volume /= mx

            except ZeroDivisionError:
                pass

            finally:
                volume *= 100

            self.audio_pike.emit(int(volume))
            self.progress.emit(int(float(i) * chunk // sample_rate))

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
