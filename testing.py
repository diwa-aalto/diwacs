"""
Created on 20.5.2013

.. moduleauthor:: Kristian
:author: Kristian

"""
# System imports
import os
import unittest


# Own imports
import controller
import filesystem
import utils
from models import Project


class TestUtils(unittest.TestCase):
    """Test utils module."""

    def setUp(self):
        unittest.TestCase.setUp(self)

    def tearDown(self):
        unittest.TestCase.tearDown(self)

    def test_passwordhash(self):
        """Test the password hash generation."""
        example_password = 'The quick brown fox jumps over the lazy dog'
        expected_hash = '2fd4e1c67a2d28fced849ee1bb76e7391b93eb12'
        myhash = utils.hash_password(example_password)
        self.assertEquals(myhash, expected_hash)

    def test_getpassword(self):
        """Test get_project_password function."""
        correct_password = 'test'
        project_id = 84
        expected_prehash = str(project_id) + correct_password
        expected_hash = utils.hash_password(expected_prehash)
        project = Project.get_by_id(project_id)
        myhash = project.password
        self.assertEquals(myhash, expected_hash)

    def test_iterislast(self):
        """Test IterIsLast function."""
        test_iterator = [5, 7, 9, 22]
        test_last = [False, False, False, True]
        index = 0
        for (item, islast) in utils.IterIsLast(test_iterator):
            self.assertEqual(test_iterator[index], item)
            self.assertEqual(test_last[index], islast)
            index += 1
        test_iterator = ['double', 'fun', 'half', 'time']
        index = 0
        for (item, islast) in utils.IterIsLast(test_iterator):
            self.assertEqual(test_iterator[index], item)
            self.assertEqual(test_last[index], islast)
            index += 1


class TestFilesystem(unittest.TestCase):
    """Test filesystem module."""

    def test_searchfile(self):
        """Test searchfile function."""
        tofind = ['api.doctree',
                  'DiWaCS.ilg',
                  '001_Edit_project_definition.pyc'
        ]
        root = os.getcwd()
        for filename in tofind:
            filepath = filesystem.search_file(filename, root)
            file_found = bool(filepath)
            self.assertTrue(file_found, '%s not found in %s' %
                            (filename, root))


class DiwaTest(unittest.TestSuite):
    """Container for unittest cases."""

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
