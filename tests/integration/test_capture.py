from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from scapy.all import DNS, DNSQR, IP, UDP, Ether, wrpcap

from common.capture import build_capture_plan


def test_capture_plan_uses_dumpcap_tshark_and_capinfos(temp_settings) -> None:
    plan = build_capture_plan(temp_settings)
    assert plan.dumpcap_command[0] == "dumpcap"
    assert plan.tshark_summary_command[0] == "tshark"
    assert plan.capinfos_command[0] == "capinfos"


def test_capture_rotation_plan(temp_settings) -> None:
    plan = build_capture_plan(temp_settings)
    assert any(item.startswith("duration:") for item in plan.dumpcap_command)
    assert any(item.startswith("filesize:") for item in plan.dumpcap_command)


def test_packet_content_assertion_with_tshark_and_capinfos(tmp_path: Path) -> None:
    if shutil.which("tshark") is None or shutil.which("capinfos") is None:
        pytest.skip("tshark/capinfos not installed")
    packet = (
        Ether()
        / IP(src="192.168.50.2", dst="1.1.1.1")
        / UDP(sport=12345, dport=53)
        / DNS(rd=1, qd=DNSQR(qname="commodore.net"))
    )
    pcap_path = tmp_path / "sample.pcap"
    wrpcap(str(pcap_path), [packet])
    tshark = subprocess.run(
        ["tshark", "-r", str(pcap_path), "-T", "fields", "-e", "dns.qry.name"],
        check=True,
        capture_output=True,
        text=True,
    )
    capinfos = subprocess.run(
        ["capinfos", str(pcap_path)], check=True, capture_output=True, text=True
    )
    assert "commodore.net" in tshark.stdout
    assert "Number of packets:" in capinfos.stdout
