import os
import json
import pytest

ROOT = "IPTVPlayer"


def test_valid_aliases():
    path = "IPTVPlayer/hosts/aliases.txt"
    assert os.path.exists(path), f"{path} missing!"

    try:
        with open(path) as f:
            data = f.read()
            data = data.replace("'", '"')
            config = json.loads(data)
    except json.JSONDecodeError as e:
        pytest.fail(f"{path} invalid: {e}")

    assert isinstance(config, dict), f"{path} should be a dictionary"


def test_valid_hostgroups():
    path = "IPTVPlayer/hosts/hostgroups.txt"
    assert os.path.exists(path), f"{path} missing!"

    allhosts = []
    for host in os.listdir("IPTVPlayer/hosts/"):
        if host.endswith(".py") and host.startswith("host"):
            allhosts.append(host[4:].replace("_blocked_", "").replace(".py", ""))

    try:
        with open(path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        pytest.fail(f"{path} invalid: {e}")

    assert isinstance(config, dict), f"{path} should be a dictionary"

    for group, hosts in config.items():
        print(f"Checking group: {group} with hosts: {hosts}")
        assert isinstance(group, str), f"Group {group} should be a string"
        assert isinstance(hosts, list), f"Hosts for group {group} should be a list"
        for host in hosts:
            assert isinstance(host, str), f"Host {host} in group {group} should be a string"
            assert host, f"Host in group {group} should not be empty"
            assert host in allhosts, f"Host {host} in group {group} not found in available hosts"
