from __future__ import annotations

import os
import socket

import pytest

pytestmark = pytest.mark.hil


def test_hil_placeholder_guard() -> None:
    if os.environ.get("C64GATE_ENABLE_HIL") != "1":
        pytest.skip("set C64GATE_ENABLE_HIL=1 to run HIL tests")
    with socket.create_connection(("c64u", 80), timeout=2):
        pass
