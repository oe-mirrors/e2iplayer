import os
import pytest

ROOT = "IPTVPlayer"


def test_valid_list():
    path = "IPTVPlayer/hosts/list.txt"
    assert os.path.exists(path), f"{path} missing!"

    alltxtHosts = []

    try:
        with open(path) as f:
            data = f.read()

        data = data.split('\n')
        for item in data:
            line = item.strip()
            if line.startswith("host"):
                alltxtHosts.append(line[4:])

    except OSError as e:
        pytest.fail(f"{path} invalid: {e}")

    allhosts = []
    for host in os.listdir("IPTVPlayer/hosts/"):
        if host.endswith(".py") and host.startswith("host"):
            allhosts.append(host[4:].replace(".py", ""))

    for host in alltxtHosts:
        if host not in allhosts:
            pytest.fail(f"Host {host} in list.txt but not found")

    for host in allhosts:
        if host not in alltxtHosts:
            pytest.fail(f"Host {host} not found in list.txt")
