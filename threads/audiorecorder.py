"""
Created on 5.6.2013

:author: neriksso

"""
# Standard imports.
from datetime import datetime
import os
from time import sleep
import wave

# Third party imports.
from pyaudio import PyAudio
from collections import deque
from wx import CallAfter

# Own imports.
import diwavars
import threads.common
from threads.diwathread import DIWA_THREAD


def logger():
    """ Get the common logger. """
    return threads.common.LOGGER


class AudioRecorder(DIWA_THREAD):
    """
    A thread for capturing audio continuously.
    It keeps a buffer that can be saved to a file.
    By convention AudioRecorder is usually written in mixed case
    even as we prefer upper case for threading types.

    :param parent: Parent of the thread.
    :type parent: :py:class:`threading.Thread`

    """
    def __init__(self, parent):
        DIWA_THREAD.__init__(self, name='AudioRecorder')
        self.parent = parent
        self.py_audio = PyAudio()
        self.stream = self.open_mic_stream()
        self.buffer = deque(maxlen=diwavars.MAX_LENGTH)

    def stop(self):
        """ Stop audio recorder. """
        DIWA_THREAD.stop(self)
        sleep(0.2)
        self.stream.close()

    def find_input_device(self):
        """ Find the microphone device. """
        for i in range(self.py_audio.get_device_count()):
            # Internationalization hack...
            # LOGGER.debug("Selecting audio device %s / %s " %
            # (str(i),str(self.py_audio.get_device_count())))
            # device_index = i
            # return device_index
            devinfo = self.py_audio.get_device_info_by_index(i)
            for keyword in ['microphone']:
                if keyword in devinfo['name'].lower():
                    return i

        default_device = self.py_audio.get_default_input_device_info()
        if default_device:
            return default_device['index']
        return None

    def open_mic_stream(self):
        """ Opens the stream object for microphone. """
        device_index = None
        # uncomment the next line to search for a device.
        # device_index = self.find_input_device()
        stream = self.py_audio.open(
            format=diwavars.FORMAT,
            channels=diwavars.CHANNELS,
            rate=diwavars.RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=diwavars.INPUT_FRAMES_PER_BLOCK
        )
        return stream

    def run(self):
        """
        Continuously record from the microphone to the buffer.

        If the buffer is full, the first frame will be removed and
        the new block appended.

        """
        while not self._stop.is_set():
            try:
                data = self.stream.read(diwavars.INPUT_FRAMES_PER_BLOCK)
                if len(self.buffer) == self.buffer.maxlen:
                    element = self.buffer.popleft()
                    del element
                self.buffer.append(data)
            except IOError, excp:
                logger().exception('Error recording: %s', str(excp))

    def save(self, ide, path):
        """Save the buffer to a file."""
        try:
            date_string = datetime.now().strftime('%d%m%Y%H%M')
            filename = '%d_%s.wav' % (ide, date_string)
            filepath = os.path.join(path, 'Audio')
            if not os.path.exists(filepath):
                os.makedirs(filepath)
            filepath = os.path.join(filepath, filename)
            sample_size = self.py_audio.get_sample_size(diwavars.FORMAT)
            wave_file = wave.open(filepath, 'wb')
            wave_file.setnchannels(diwavars.CHANNELS)
            wave_file.setsampwidth(sample_size)
            wave_file.setframerate(diwavars.RATE)
            wave_file.writeframes(b''.join(self.buffer))
            wave_file.close()
            CallAfter(self.parent.ClearStatusText)
        except:
            logger().exception('audio save exception')
            CallAfter(self.parent.ClearStatusText)
