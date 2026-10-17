from pathlib import Path

from PIL import Image

import instacards.qc as qc
from instacards.editorial import CANVAS
from instacards.qc import build_manifest, make_contact_sheet


def test_qc_outputs_manifest_and_contact_sheet(tmp_path: Path) -> None:
    cards = tmp_path / "cards"
    cards.mkdir()
    for index in range(1, 3):
        Image.new("RGB", CANVAS, (index * 30, 50, 90)).save(cards / f"{index:02d}.jpg")
    manifest_path = tmp_path / "qc" / "manifest.json"

    manifest = build_manifest(cards, manifest_path)
    make_contact_sheet(cards, tmp_path / "qc" / "contact-sheet.jpg", columns=2)

    assert manifest["items"][0]["technical_pass"] is True
    assert len(manifest["items"][0]["sha256"]) == 71
    assert manifest_path.is_file()
    assert (tmp_path / "qc" / "contact-sheet.jpg").is_file()


def test_contact_sheet_label_preserves_nonsequential_slide_number() -> None:
    assert qc.contact_sheet_label(Path("06.jpg")) == "06"
