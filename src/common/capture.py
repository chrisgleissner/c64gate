from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common.settings import Settings


@dataclass(slots=True)
class CapturePlan:
    dumpcap_command: list[str]
    tshark_summary_command: list[str]
    capinfos_command: list[str]


def build_capture_plan(settings: Settings) -> CapturePlan:
    pcap_path = Path(settings.pcap_dir) / "device-capture.pcapng"
    return CapturePlan(
        dumpcap_command=[
            "dumpcap",
            "-i",
            settings.capture_interface,
            "-b",
            f"duration:{settings.capture_rotation_seconds}",
            "-b",
            f"filesize:{settings.capture_rotation_megabytes * 1024}",
            "-b",
            f"files:{settings.capture_ring_files}",
            "-w",
            str(pcap_path),
        ],
        tshark_summary_command=["tshark", "-r", str(pcap_path), "-T", "json"],
        capinfos_command=["capinfos", str(pcap_path)],
    )
