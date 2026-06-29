"""Smoke tests for the package scaffold. Real tests arrive with M1."""

import tinca_tag
from tinca_tag.cli import main
from tinca_tag.endpoint import Endpoint


def test_package_imports():
    assert tinca_tag.__version__


def test_cli_entry_runs():
    assert main([]) == 0


def test_endpoint_is_frozen_dataclass():
    ep = Endpoint(host="192.168.1.50", port=9090, protocol="rosbridge", secure=False)
    assert ep.host == "192.168.1.50"
    assert ep.protocol == "rosbridge"
