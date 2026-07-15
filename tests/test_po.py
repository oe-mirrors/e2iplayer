import glob
import shutil
import subprocess

import pytest

PO_FILES = sorted(glob.glob("IPTVPlayer/locale/*/LC_MESSAGES/*.po"))


def test_po_files_found():
    assert PO_FILES, "no .po files found under IPTVPlayer/locale"


@pytest.mark.skipif(shutil.which("msgfmt") is None, reason="msgfmt (gettext) not installed")
@pytest.mark.parametrize("po_path", PO_FILES)
def test_po_file_valid(po_path):
    result = subprocess.run(
        ["msgfmt", "--check", "--check-format", "-o", "/dev/null", po_path],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{po_path} invalid:\n{result.stderr}"
