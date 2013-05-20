'''
Created on 20.5.2013

@author: Kristian
'''
import unittest

import commons
import filesystem


class TestCommons(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)

    def tearDown(self):
        unittest.TestCase.tearDown(self)

    def test_passwordhash(self):
        """ Test the SHA1 password hash generation. """
        example_password = "The quick brown fox jumps over the lazy dog"
        expected_hash = "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12"
        myhash = commons.HashPassword(example_password)
        self.assertEquals(myhash, expected_hash)

    def test_getpassword(self):
        correct_password = "test"
        project_id = 84
        expected_prehash = str(project_id) + correct_password
        expected_hash = commons.HashPassword(expected_prehash)
        myhash = commons.GetProjectPassword(project_id)
        self.assertEquals(myhash, expected_hash)


class TestFilesystem(unittest.TestCase):

    def test_setvars(self):
        up_url = "www.dummy_url_for_test.org"
        up_user = "tester"
        up_pass = "testpassword"
        self.assertNotEquals(filesystem.CAMERA_URL, up_url)
        self.assertNotEquals(filesystem.CAMERA_USER, up_user)
        self.assertNotEquals(filesystem.CAMERA_PASS, up_pass)
        old_vars = (filesystem.CAMERA_URL, filesystem.CAMERA_USER,
                    filesystem.CAMERA_PASS)
        filesystem.UpdateCameraVars(up_url, up_user, up_pass)
        self.assertTrue(filesystem.CAMERA_URL == up_url)
        self.assertEquals(filesystem.CAMERA_USER, up_user)
        self.assertEquals(filesystem.CAMERA_PASS, up_pass)
        filesystem.UpdateCameraVars(old_vars[0], old_vars[1], old_vars[2])
        self.assertTrue(filesystem.CAMERA_URL == old_vars[0])
        self.assertEquals(filesystem.CAMERA_USER, old_vars[1])
        self.assertEquals(filesystem.CAMERA_PASS, old_vars[2])


class DiwaTest(unittest.TestSuite):

    def __init__(self):
        print 'DiwaTest__init__'
        unittest.TestSuite.__init__(self, test=(
                TestCommons
            )
        )

    def run(self, result, debug=False):
        return unittest.TestSuite.run(self, result, debug=debug)


if __name__ == "__main__":
    unittest.main(verbosity=2)
