"""
The production image installs CPU-only PyTorch.

`torch` from the default package index on Linux pulls NVIDIA CUDA packages,
several gigabytes the production image can never use because it runs on CPU
instances. That means a much larger image, slower builds and deploys, and more
disk -- for nothing. The Dockerfile installs the CPU build from PyTorch's own
index first, and `pip install -r requirements.txt` then treats `torch==X` as
already satisfied, because PEP 440 ignores the `+cpu` local label when
comparing against a pin without one.

Docker is not available on the development machine, so these tests guard the
Dockerfile's shape and its link to requirements.txt; the build itself is proven
on the first real image build. They cannot check that the CPU index publishes
the pinned version. That was verified by hand when this was written:
`pip index versions torch --index-url https://download.pytorch.org/whl/cpu
--platform manylinux_2_28_x86_64 --python-version 3.14 --only-binary=:all:`
listed 2.12.0+cpu.
"""
import io
import re
import subprocess

from django.test import SimpleTestCase

CPU_INDEX = 'https://download.pytorch.org/whl/cpu'


def _read(path):
    return io.open(path, encoding='utf-8').read()


class CpuOnlyTorchImageTests(SimpleTestCase):

    def setUp(self):
        self.dockerfile = _read('Dockerfile')
        self.requirements = _read('requirements.txt')

    def test_torch_is_installed_from_the_cpu_index(self):
        self.assertIn(CPU_INDEX, self.dockerfile)

    def test_cpu_torch_is_installed_before_the_requirements(self):
        """Order matters: installed after, pip would already have pulled the CUDA build."""
        cpu_install = self.dockerfile.find(CPU_INDEX)
        requirements_install = self.dockerfile.find('-r requirements.txt')
        self.assertNotEqual(cpu_install, -1)
        self.assertNotEqual(requirements_install, -1)
        self.assertLess(cpu_install, requirements_install)

    def test_requirements_pin_torch_exactly_so_the_dockerfile_can_read_it(self):
        pins = re.findall(r'(?im)^torch==([0-9][^\s;]*)\s*$', self.requirements)
        self.assertEqual(len(pins), 1,
                         'requirements.txt must pin torch exactly once, as torch==X.Y.Z')

    def test_the_dockerfile_reads_the_version_the_same_way_requirements_pin_it(self):
        """
        Runs the Dockerfile's own extraction pipeline against the real
        requirements.txt, so a change to either side fails here instead of in a
        production build. Skipped where the POSIX tools it uses are missing.
        """
        match = re.search(r'TORCH_VERSION="\$\((?P<cmd>.+?)\)"', self.dockerfile)
        self.assertIsNotNone(match, 'could not find the TORCH_VERSION extraction in the Dockerfile')
        try:
            result = subprocess.run(['bash', '-c', match.group('cmd')],
                                    capture_output=True, text=True, timeout=30)
        except (FileNotFoundError, OSError):
            self.skipTest('bash is not available to run the extraction')
        extracted = result.stdout.strip()
        expected = re.search(r'(?im)^torch==([0-9][^\s;]*)\s*$', self.requirements).group(1)
        self.assertEqual(extracted, expected)
