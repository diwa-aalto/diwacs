"""
Created on 20.5.2013

:author: Kristian

"""
# System imports
from decimal import Decimal
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
        """
        Do nothing if the object is called.

        :TODO:
            Log the call with method name (possibly create new
            CallAbsorber with argument name when using get
            attribute to create unique absorbers).

        """
        pass

    def __getattribute__(self, *args, **kwargs):
        """
        Get attribute by name.

        """
        return CallAbsorber()

    def __setattr__(self, *args, **kwargs):
        """
        Set attribute value by name.

        """
        pass

    def __repr__(self):
        """
        Return the call_absorber string.

        """
        return 'CallAbsorber {0}'.format(hash(self))

    def __hash__(self, *args, **kwargs):
        """
        Returns the order number of object creation of the type
        CallAbsorber of this instance.

        """
        try:
            return int(self.number)
        except Exception:
            return 0


class TestAudioRecorder(unittest.TestCase):
    """
    Test audio recorder module.

    """
    def setUp(self):
        """
        Set up the audio recorder helpers for testing.

        """
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
        """Stub to add cleaners in."""
        pass

    def test_record(self):
        """
        Test recording functionality of AudioRecorder.

        """
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
        """Stub to add helpers in."""
        pass

    def tearDown(self):
        """Stub to add cleaners in."""
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
        """Stub to add helpers in."""
        pass

    def tearDown(self):
        """Stub to add cleaners in."""
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
        tonotfind = [
            'NOT_EXISTING.log',
            'exists_not.exe',
            'True',
            'False',
            'COM1',         # This is evil!
            'IOError',
            ''
        ]
        root = os.getcwd()
        for filename in tofind:
            filepath = filesystem.search_file(filename, root)
            file_found = bool(filepath)
            assertion_error = '{0} not found in {1}'
            self.assertTrue(file_found, assertion_error.format(filename, root))
        for filename in tonotfind:
            error = None
            try:
                filepath = filesystem.search_file(filename, root)
                file_found = bool(filepath)
                assertion_error = ('{0} found in {1} although it does not '
                                   'exists anywhere!')
                self.assertFalse(file_found, assertion_error.format(filename,
                                                                    root))
            except Exception as excp:
                error = excp
            self.assertIs(error, None, 'Error')


class TestDocumentation(unittest.TestCase):
    """
    Test that every Python function has been documented.

    """
    def setUp(self):
        """Stub to add helpers in."""
        self.target_folders = ['.', 'controller', 'threads']
        self.target_types = ['.py']
        self.ignore_methods = ['__init__']

    def tearDown(self):
        """Stub to add cleaners in."""
        pass

    def test_documentation(self):
        """
        Test that most of the code has been documented.

        :note:
            The algorithm that calculates the documentation percentage
            is not perfect but kind of works. It could be improved
            by using actual parser (and pylint even does the same) but
            this makes it an actual testcase.

            This also prints out the missed lines where there should have
            been documentation (docstrings) and prints the total percentage
            of the project documented.

            This test fails if the percentage is lower than a hard-coded
            expected value. That value defaults to 95% at this moment.

        """
        files = []
        for folder in self.target_folders:
            items = os.listdir(folder)
            for item in items:
                if not os.path.isfile(item):
                    continue
                if os.path.splitext(item)[1] in self.target_types:
                    files.append(item)
        total_definitions = 0
        documented_definitions = 0
        misses = []
        for filename in files:
            last_line_was_definition = False
            definition_ended = True
            fin = open(filename, 'r')
            try:
                for index, line in enumerate(fin):
                    stripped = str(line).strip()
                    if (stripped.startswith('class ') or
                            stripped.startswith('def ')):
                        should_skip = False
                        for ignore in self.ignore_methods:
                            if ignore in stripped:
                                should_skip = True
                        if not should_skip:
                            last_line_was_definition = True
                            total_definitions += 1
                            if ':' not in line:
                                definition_ended = False
                            continue
                    if not definition_ended:
                        if ':' in line:
                            definition_ended = True
                            continue
                    if last_line_was_definition and ('"""' in line):
                        documented_definitions += 1
                    elif last_line_was_definition:
                        misses.append('{0}:{1}'.format(filename, index + 1))
                    last_line_was_definition = False
            finally:
                fin.close()
        percentage = (Decimal(100) * Decimal(documented_definitions) /
                      Decimal(total_definitions))
        print 'HIT RATE {0:.4}%'.format(percentage)
        if percentage < Decimal(100):
            print 'MISSED:'
            for miss in misses:
                print miss
        # Expect at least 95% to be documented.
        on_fail = 'I find your documentation lacking!'
        self.assertGreaterEqual(percentage, Decimal(95), on_fail)


class TestDiwa(unittest.TestSuite):
    """
    Container for unittest cases.

    """
    def __init__(self):
        tests = (TestUtils, TestFilesystem, TestAudioRecorder)
        unittest.TestSuite.__init__(self, tests)

    def run(self, result, debug=False):
        """Run the unittest."""
        return unittest.TestSuite.run(self, result, debug=debug)


if __name__ == "__main__":
    unittest.main(verbosity=2)
