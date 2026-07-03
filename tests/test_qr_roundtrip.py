"""CP-B: QR integrity. Render -> decode == exact contract string.

Renders the QR to PNG, decodes it back, and asserts the decoded payload equals the
deep-link URL byte-for-byte at the ADR-0002 error level (H). If a centered logo is
added later, this is the test that proves it still decodes.
"""

import io

import pytest

from tinca_tag.endpoint import Endpoint
from tinca_tag.render.qr import png_bytes
from tinca_tag.render.url import connect_url

zxingcpp = pytest.importorskip("zxingcpp")
PIL_Image = pytest.importorskip("PIL.Image")

CASES = [
    Endpoint(host="192.168.1.50", port=9090, protocol="rosbridge", secure=False),
    Endpoint(host="192.168.1.50", port=8765, protocol="foxglove-ws", secure=True),
    Endpoint(host="robot.local", port=9999, protocol="foxglove-ws", secure=False),
    Endpoint(host="10.0.0.2", port=9090, protocol="rosbridge", secure=True),
]


def _decode(png: bytes) -> str:
    image = PIL_Image.open(io.BytesIO(png))
    results = zxingcpp.read_barcodes(image)
    assert results, "no barcode decoded from rendered QR"
    return results[0].text


@pytest.mark.parametrize("endpoint", CASES)
def test_qr_roundtrip(endpoint):
    url = connect_url(endpoint)
    assert _decode(png_bytes(url)) == url


def test_qr_roundtrip_with_name():
    url = connect_url(
        Endpoint(host="192.168.1.50", port=9090, protocol="rosbridge", secure=False),
        name="Spot 7",
    )
    assert _decode(png_bytes(url)) == url
