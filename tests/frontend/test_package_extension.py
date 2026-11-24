import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import package_extension


class PackageExtensionTest(unittest.TestCase):
    def test_build_uses_only_the_runtime_allowlist_and_repeats_without_overwriting_extras(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            output = root / "package"
            shutil.copytree(package_extension.SOURCE, source)
            (source / "modules" / "local-fixture.js").write_text("// local fixture", encoding="utf-8")
            (source / "local-fixture.json").write_text("{}", encoding="utf-8")

            with patch.object(package_extension, "SOURCE", source):
                first_count = package_extension.build_extension(output)
                self.assertEqual(first_count, package_extension.build_extension(output))
                self.assertFalse((output / "modules" / "local-fixture.js").exists())
                self.assertFalse((output / "local-fixture.json").exists())
                self.assertTrue((output / "modules" / "result-view.js").is_file())
                local = output / "local-note.txt"
                local.write_text("Local output", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    package_extension.build_extension(output)
                self.assertEqual(local.read_text(encoding="utf-8"), "Local output")


if __name__ == "__main__":
    unittest.main()
