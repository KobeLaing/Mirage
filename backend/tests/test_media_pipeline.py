import io

import pytest
from PIL import Image

from app.errors import PayloadTooLarge, UnsupportedMediaType
from app.media import pipeline, sniff
from tests.conftest import SEED_MEDIA, WEBM_HEADER, gps_exif, make_jpeg, make_png, make_webp

LIMITS = pipeline.MediaLimits(max_image_bytes=200_000, max_video_bytes=400_000, max_image_pixels=4_000_000)


@pytest.fixture
def workdir(tmp_path):
    return tmp_path


def run(data: bytes, workdir, limits=LIMITS):
    return pipeline.process(io.BytesIO(data), limits, workdir)


def test_sniff_known_types():
    assert sniff.detect(make_jpeg()) is sniff.JPEG
    assert sniff.detect(make_png()) is sniff.PNG
    assert sniff.detect((SEED_MEDIA / "ai-video-1.mp4").read_bytes()[:64]) is sniff.MP4


@pytest.mark.parametrize(
    "payload",
    [
        b"<!DOCTYPE html><script>alert(1)</script>",
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"%PDF-1.7\n...",
        b"MZ\x90\x00 windows executable",
        b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00",  # HEIC image in an MP4-like container
    ],
)
def test_disallowed_content_is_rejected(payload, workdir):
    with pytest.raises(UnsupportedMediaType):
        run(payload, workdir)


def test_allow_list_is_exactly_jpeg_png_gif_mp4():
    assert {t.mime for t in sniff.ALL_TYPES} == {"image/jpeg", "image/png", "image/gif", "video/mp4"}


def test_real_webp_rejected(workdir):
    data = make_webp()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"  # a genuine WebP file
    with pytest.raises(UnsupportedMediaType):
        run(data, workdir)


def test_real_webm_rejected(workdir):
    assert b"webm" in WEBM_HEADER
    with pytest.raises(UnsupportedMediaType):
        run(WEBM_HEADER + b"\x00" * 64, workdir)


def test_gif_accepted(workdir):
    buf = io.BytesIO()
    Image.new("P", (16, 16)).save(buf, "GIF")
    result = run(buf.getvalue(), workdir)
    assert (result.kind, result.mime) == ("image", "image/gif")


def test_empty_file_rejected(workdir):
    with pytest.raises(UnsupportedMediaType):
        run(b"", workdir)


def test_oversized_image_rejected(workdir):
    noisy = Image.effect_noise((400, 400), 100).convert("RGB")
    buf = io.BytesIO()
    noisy.save(buf, "PNG")
    assert len(buf.getvalue()) > LIMITS.max_image_bytes
    with pytest.raises(PayloadTooLarge):
        run(buf.getvalue(), workdir)


def test_stream_cut_off_past_hard_cap(workdir):
    with pytest.raises(PayloadTooLarge):
        run(b"\xff\xd8\xff" + b"\x00" * (LIMITS.max_video_bytes + 10), workdir)


def test_exif_and_gps_are_stripped(workdir):
    original = make_jpeg(exif=gps_exif())
    with Image.open(io.BytesIO(original)) as img:
        assert img.getexif().get(0x8825)  # the fixture really has GPS

    result = run(original, workdir)
    with Image.open(result.open()) as img:
        assert dict(img.getexif()) == {}
        assert "exif" not in img.info
    assert b"SpyCam" not in result.open().read()


def test_trailing_payload_dropped_by_reencode(workdir):
    polyglot = make_jpeg() + b"<script>alert(1)</script>"
    result = run(polyglot, workdir)
    assert b"<script>" not in result.open().read()


def test_corrupt_image_rejected(workdir):
    with pytest.raises(UnsupportedMediaType):
        run(b"\xff\xd8\xff\xe0" + b"garbage" * 50, workdir)


def test_decompression_bomb_rejected(workdir):
    limits = pipeline.MediaLimits(max_image_bytes=200_000, max_video_bytes=400_000, max_image_pixels=10_000)
    with pytest.raises(UnsupportedMediaType):
        run(make_png(size=(200, 200)), workdir, limits)


def test_mp4_with_appended_junk_rejected(workdir):
    data = (SEED_MEDIA / "ai-video-1.mp4").read_bytes() + b"<html><script>alert(1)</script></html>"
    with pytest.raises(UnsupportedMediaType):
        run(data, workdir)


def test_valid_video_accepted(workdir):
    result = run((SEED_MEDIA / "ai-video-1.mp4").read_bytes(), workdir)
    assert (result.kind, result.mime, result.ext) == ("video", "video/mp4", "mp4")


def test_image_dimensions_recorded(workdir):
    result = run(make_jpeg(size=(120, 80)), workdir)
    assert (result.width, result.height) == (120, 80)
