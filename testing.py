'''
Created on 20.5.2013

@author: Kristian
'''
# System imports
import os
import unittest


# Own imports
import controller
import filesystem
import utils


class TestUtils(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)

    def tearDown(self):
        unittest.TestCase.tearDown(self)

    def test_passwordhash(self):
        """ Test the SHA1 password hash generation. """
        example_password = "The quick brown fox jumps over the lazy dog"
        expected_hash = "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12"
        myhash = utils.HashPassword(example_password)
        self.assertEquals(myhash, expected_hash)

    def test_getpassword(self):
        correct_password = "test"
        project_id = 84
        expected_prehash = str(project_id) + correct_password
        expected_hash = utils.HashPassword(expected_prehash)
        myhash = controller.GetProjectPassword(project_id)
        self.assertEquals(myhash, expected_hash)

    def test_iterislast(self):
        testIterator = [5, 7, 9, 22]
        testLast = [False, False, False, True]
        x = 0
        for (item, islast) in utils.IterIsLast(testIterator):
            self.assertEqual(testIterator[x], item)
            self.assertEqual(testLast[x], islast)
            x += 1
        testIterator = ['double', 'fun', 'half', 'time']
        x = 0
        for (item, islast) in utils.IterIsLast(testIterator):
            self.assertEqual(testIterator[x], item)
            self.assertEqual(testLast[x], islast)
            x += 1


class TestFilesystem(unittest.TestCase):

    def test_searchfile(self):
        tofind = ['api.doctree', 'DiWaCS.ilg',
                  '001_Edit_project_definition.pyc']
        root = os.getcwd()
        for f in tofind:
            fp = filesystem.SearchFile(f, root)
            if not fp:
                self.assertFalse(True, '%s not found in %s' % (f, root))


class DiwaTest(unittest.TestSuite):

    def __init__(self):
        print 'DiwaTest__init__'
        unittest.TestSuite.__init__(self, test=(
                TestUtils
            )
        )

    def run(self, result, debug=False):
        return unittest.TestSuite.run(self, result, debug=debug)


if __name__ == "__main__":
    unittest.main(verbosity=2)
