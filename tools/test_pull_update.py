import hashlib
import io
import tarfile
import unittest
from pull_update import validate_archive

def package(name, data=b'test', kind=tarfile.REGTYPE):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        item = tarfile.TarInfo(name)
        item.type = kind
        item.size = len(data) if kind == tarfile.REGTYPE else 0
        archive.addfile(item, io.BytesIO(data))
    return output.getvalue()

class Validation(unittest.TestCase):
    def test_valid(self):
        validate_archive(package('pilot-beta/beta.js'), {'pilot-beta/beta.js': hashlib.sha256(b'test').hexdigest()}, 'pi03')

    def test_wrong_board(self):
        with self.assertRaises(ValueError):
            validate_archive(package('pilot/beta.js'), {}, 'pi03')

    def test_traversal(self):
        with self.assertRaises(ValueError):
            validate_archive(package('pilot-beta/../../etc/passwd'), {}, 'pi03')

    def test_link(self):
        with self.assertRaises(ValueError):
            validate_archive(package('pilot-beta/link', kind=tarfile.SYMTYPE), {}, 'pi03')

    def test_hash(self):
        with self.assertRaises(ValueError):
            validate_archive(package('pilot-beta/beta.js'), {'pilot-beta/beta.js': 'bad'}, 'pi03')

if __name__ == '__main__':
    unittest.main()
