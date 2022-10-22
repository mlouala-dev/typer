# بسم الله الرحمان الرحيم
"""
All the QThread elements we use for asynchronous works
"""
import re
import os
import win32api
import wave
import pyaudio
from pydub import AudioSegment
from time import localtime, strftime
from id3parse import ID3, ID3TextFrame

from PyQt6.QtCore import QThread, pyqtSignal, QRunnable
from PyQt6.QtGui import QTextDocument

from tools import G, S, T


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


class AudioConverter(QRunnable):
    name = 'AudioConverter'

    def __init__(self, filepath):
        super().__init__()
        self.filepath = os.path.join(S.GLOBAL.audio_record_path, f'{filepath}.wav')

    def run(self):
        new_path = self.filepath.replace('.wav', '.ogg')
        audiofile = AudioSegment.from_wav(self.filepath)
        audiofile.export(new_path)

        os.remove(self.filepath)
        S.POOL.start(AudioMap.FileProbe(new_path, S.GLOBAL.AUDIOMAP.digest))

        self.done(self.name)


class AudioMap(QRunnable):
    name = 'AudioMap'

    class FileProbe(QRunnable):
        name = 'FileProbe'

        def __init__(self, file, callback_fn):
            self.filepath = file
            self.callback_fn = callback_fn
            super().__init__()

        def run(self):
            path, file = os.path.split(self.filepath)
            file = os.path.splitext(file)[0]
            id3 = ID3.from_file(self.filepath)

            try:
                duration = int(id3.find_frame_by_name('TPE1').text)

            except ValueError:
                G.warning(f'duration not found for "{file}", searching')
                duration = AudioSegment.from_file(self.filepath).duration_seconds
                id3.add_frame(ID3TextFrame.from_scratch('TPE1', str(int(duration))))

            finally:
                id3.to_file()

            real_time = int(file.split('_')[0])
            time_str = strftime('%Y-%m-%d %H:%M:%S', localtime(real_time))

            self.callback_fn({
                'path': self.filepath,
                'min': real_time - duration,
                'max': real_time,
                'time': time_str,
                'duration': duration
            })

            self.done(self.name)

    def __init__(self, folder):
        self.folder = folder
        self.map = {}
        super().__init__()

    def run(self):
        for dirpath, dirnames, filenames in os.walk(self.folder):
            for file in filter(lambda x: x.endswith('.ogg'), filenames):
                path = os.path.join(dirpath, file)
                S.POOL.start(self.FileProbe(path, self.digest))

        self.done(self.name)

    def digest(self, obj):
        self.map[obj['max']] = obj

    def find(self, realtime) -> int:
        for t in sorted(self.map.keys()):
            if t > realtime:
                break
        else:
            return -1

        if realtime > self.map[t]['min']:
            return t

        return -1

    def play(self, index, realtime):
        # manual ajustment 5 sec before
        time = realtime - self.map[index]['min'] - 5

        # TODO define software from settings
        win32api.ShellExecute(0, "open", r'C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe', f'"{self.map[index]["path"]}" /seek={int(time)}', None, 1)


class graphBlockMap(QRunnable):
    name = 'graphBlockMap'

    def __init__(self, document: QTextDocument, callback_fn):
        self.callback_fn = callback_fn
        self.doc = document.clone()

        super().__init__()

    def run(self):
        self.doc.size()
        map = {}

        for block_id in range(self.doc.blockCount()):
            block = self.doc.findBlockByNumber(block_id)
            map[block_id] = (block.layout().position().y() + 1, block.layout().boundingRect().height() - 2)

        self.callback_fn(map)
        self.done(self.name)


class solveAudioMapping(QRunnable):
    name = 'solveAudioMapping'

    def __init__(self, html: str, callback_fn):
        self.callback_fn = callback_fn
        self.html = re.split('<body.*?>', html)[-1].split('\n')

        super().__init__()

    def run(self):
        blocks = {}

        for i, html_block in enumerate(self.html):
            if T.HTML.hasParagraphTime(html_block):
                solve = S.GLOBAL.AUDIOMAP.find(T.HTML.paragraphTime(html_block))
                blocks[i - 1] = solve
            else:
                blocks[i - 1] = -2

        self.callback_fn(blocks)
        self.done(self.name)
