import os
import shutil
import tempfile
import unittest

from core.tools import dispatch, get_schemas
from core.tools.system import is_leap_year


class LeapYearTest(unittest.TestCase):
    def test_leap_years(self):
        self.assertIn("是闰年", is_leap_year(2000))
        self.assertIn("是闰年", is_leap_year(2024))

    def test_common_years(self):
        self.assertIn("不是闰年", is_leap_year(1900))
        self.assertIn("不是闰年", is_leap_year(2023))

    def test_dispatch(self):
        self.assertIn("是闰年", dispatch("isLeapYear", {"year": 2024}))

    def test_schema_count(self):
        self.assertEqual(len(get_schemas()), 12)


class FileOpsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.sub = os.path.join(self.base, "sub")
        self.file = os.path.join(self.sub, "a.txt")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_full_lifecycle(self):
        dispatch("createDirectory", {"path": self.sub})
        self.assertTrue(os.path.isdir(self.sub))

        dispatch("createFile", {"directory": self.sub, "filename": "a.txt", "content": "第一行"})
        self.assertTrue(os.path.isfile(self.file))
        self.assertEqual(dispatch("readTextFile", {"path": self.file}), "第一行")
        self.assertEqual(dispatch("getFileType", {"path": self.file}), ".txt")

        dispatch("editTextFile", {"path": self.file, "content": "\n第二行", "mode": "append"})
        self.assertEqual(dispatch("readTextFile", {"path": self.file}), "第一行\n第二行")

        listing = dispatch("listDirectory", {"path": self.sub})
        self.assertIn("[FILE] a.txt", listing)

        dispatch("renamePath", {"path": self.file, "newName": "b.txt"})
        self.assertTrue(os.path.isfile(os.path.join(self.sub, "b.txt")))

        dispatch("deleteFile", {"path": os.path.join(self.sub, "b.txt")})
        self.assertFalse(os.path.isfile(os.path.join(self.sub, "b.txt")))

        dispatch("deleteDirectory", {"path": self.base})
        self.assertFalse(os.path.exists(self.base))

    def test_unknown_tool(self):
        self.assertIn("未知工具", dispatch("nope", {}))


if __name__ == "__main__":
    unittest.main()
