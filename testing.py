"""
Created on 20.5.2013

:author: Kristian

"""
# System imports
import os
from datetime import datetime
from time import sleep
from threading import RLock
import unittest


# Own imports
import filesystem
from utils import IterIsLast
from threads import audiorecorder


class CallAbsorber(object):
    """
    Substitute for GUIs.

    """
    NUMBER = int(1)
    MYLOCK = RLock()

    def __init__(self):
        self.number = 0
        with CallAbsorber.MYLOCK:
            if CallAbsorber.NUMBER is None:
                CallAbsorber.NUMBER = 1
            self.number = int(CallAbsorber.NUMBER)
            CallAbsorber.NUMBER += 1

    def __call__(self, *args, **kwargs):
        pass

    def __getattribute__(self, *args, **kwargs):
        return CallAbsorber()

    def __setattr__(self, *args, **kwargs):
        pass

    def __str__(self):
        return 'CallAbsorber {0}'.format(hash(self))

    def __unicode__(self):
        return u'CallAbsorber {0}'.format(hash(self))

    def __hash__(self, *args, **kwargs):
        """
        Returns the order number of object creation of the type
        CallAbsorber of this instance.

        """
        try:
            return int(self.number)
        except:
            return 0


class TestAudioRecorder(unittest.TestCase):
    """
    Test audio recorder module.

    """
    def setUp(self):
        timeform = str(datetime.now().isoformat())
        timeform = timeform[:timeform.rfind('.')]
        replaces = (('-', ''), (':', ''), ('T', '_'))
        for rule in replaces:
            timeform = timeform.replace(*rule)
        self.gui = CallAbsorber()
        self.tpath = os.path.join(os.getcwd(), 'TEST_PROJECT')
        frmt = (timeform,
                hash(self.gui),
                os.environ['USERNAME'])
        xten = '_'.join(['{' + str(i) + '}' for i in xrange(3)])
        self.guid = xten.format(*frmt)
        unittest.TestCase.setUp(self)

    def tearDown(self):
        pass

    def testRecord(self):
        error = None
        try:
            recorder = audiorecorder.AudioRecorder(self.gui)
            recorder.start()
            sleep(0.75)
            recorder.save(self.guid, self.tpath)
            recorder.stop()
        except IOError as excp:
            error = excp
        self.assertIs(error, None, 'No input device?')


class TestUtils(unittest.TestCase):
    """
    Test utils module.

    """
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_iterislast(self):
        """
        Test IterIsLast function.

        """
        test_iterator = [5, 7, 9, 22]
        test_last = [False, False, False, True]
        index = 0
        for (item, islast) in IterIsLast(test_iterator):
            self.assertEqual(test_iterator[index], item)
            self.assertEqual(test_last[index], islast)
            index += 1
        test_iterator = ['double', 'fun', 'half', 'time']
        index = 0
        for (item, islast) in IterIsLast(test_iterator):
            self.assertEqual(test_iterator[index], item)
            self.assertEqual(test_last[index], islast)
            index += 1


class TestFilesystem(unittest.TestCase):
    """
    Test filesystem module.

    """
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_searchfile(self):
        """
        Test searchfile function.

        """
        tofind = [
            'api.doctree',
            'DiWaCS.ilg',
            '001_Edit_project_definition.pyc'
        ]
        root = os.getcwd()
        for filename in tofind:
            filepath = filesystem.search_file(filename, root)
            file_found = bool(filepath)
            assertion_error = '{0} not found in {1}'
            self.assertTrue(file_found, assertion_error.format(filename, root))


class DiwaTest(unittest.TestSuite):
    """
    Container for unittest cases.

    """

    def __init__(self):
        tests = (TestUtils, TestFilesystem, TestAudioRecorder)
        unittest.TestSuite.__init__(self, tests)

    def run(self, result, debug=False):
        return unittest.TestSuite.run(self, result, debug=debug)


if __name__ == "__main__":
    unittest.main(verbosity=2)
