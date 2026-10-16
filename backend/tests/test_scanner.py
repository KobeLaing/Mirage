"""AI Authenticity Scanner: API behaviour, detectors, combination rules, registry safety."""

import io
import socket
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, PngImagePlugin

from app.scanner import registry
from app.scanner.analysis import noise_stats, periodic_peak_z
from app.scanner.base import Detector, DetectorResult
from app.scanner.combine import CombineConfig, combine
from app.scanner.detectors.temporal import unexplained_change
from app.schemas.scanner import NOTICE
from tests.conftest import FRONTEND_ORIGIN, KARA, KOBE, SEED_MEDIA, as_user, make_jpeg, make_webp

URL = "/api/v1/scanner"


def scan(client, data: bytes, filename="file.jpg", content_type="image/jpeg", user=KOBE):
    return client.post(URL, headers=as_user(user), files={"file": (filename, data, content_type)})


def signal(body, name):
    return next(s for s in body["signals"] if s["detector"] == name)


# --- Results on real files -----------------------------------------------------------

def test_signed_c2pa_ai_claim_is_decisive(seeded_client):
    """AIoasis.jpg carries a Google-signed C2PA manifest saying it was AI-generated."""
    r = scan(seeded_client, (SEED_MEDIA / "AIoasis.jpg").read_bytes())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "likely_ai" and body["verdict_label"] == "Likely AI-generated"
    assert body["score"] >= 95
    c2pa = signal(body, "c2pa")
    assert c2pa["status"] == "ok" and c2pa["conclusive"] and "Google" in c2pa["explanation"]
    assert body["notice"] == NOTICE


def test_no_conclusive_signal_says_inconclusive_without_a_score(seeded_client):
    """A scanned painting with no metadata: nothing conclusive, so no number is shown."""
    r = scan(seeded_client, (SEED_MEDIA / "realpainting4.jpg").read_bytes())
    body = r.json()
    assert body["verdict"] == "inconclusive"
    assert body["verdict_label"] == "Inconclusive"
    assert body["score"] is None
    assert body["notice"] == NOTICE
    assert signal(body, "c2pa")["status"] == "no_signal"


def test_generator_name_in_png_metadata(seeded_client):
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", "a cat\nSteps: 30, Sampler: Euler a, CFG scale: 7, Seed: 1, Model: sdxl")
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), (120, 90, 60)).save(buf, "PNG", pnginfo=info)
    body = scan(seeded_client, buf.getvalue(), "x.png", "image/png").json()
    meta = signal(body, "metadata")
    assert meta["conclusive"] and meta["score"] >= 90
    assert body["verdict"] == "likely_ai"


def test_camera_exif_leans_real(seeded_client):
    exif = Image.Exif()
    exif[0x010F], exif[0x0110] = "Canon", "EOS R6"
    exif_ifd = {0x829A: (1, 250), 0x829D: (28, 10), 0x8827: 400}
    exif[0x8769] = exif_ifd
    body = scan(seeded_client, make_jpeg(size=(300, 300), exif=exif.tobytes())).json()
    meta = signal(body, "metadata")
    assert meta["conclusive"] and meta["score"] <= 30
    assert "Canon EOS R6" in meta["explanation"]


def test_video_scan_runs_video_detectors_only(seeded_client):
    body = scan(seeded_client, (SEED_MEDIA / "real-video-1.mp4").read_bytes(), "v.mp4", "video/mp4").json()
    assert body["media_kind"] == "video"
    names = {s["detector"] for s in body["signals"]}
    assert {"c2pa", "video_container", "video_frames", "temporal"} <= names
    assert not names & {"metadata", "frequency", "noise", "ela"}
    assert "face_swap" not in names  # off by default
    assert body["notice"] == NOTICE


# --- Upload safety -------------------------------------------------------------------

@pytest.mark.parametrize("data, name, ctype", [
    (b"<html><script>alert(1)</script></html>", "x.jpg", "image/jpeg"),
    (make_webp(), "x.webp", "image/webp"),
])
def test_same_type_checks_as_posts(seeded_client, data, name, ctype):
    assert scan(seeded_client, data, name, ctype).status_code == 415


def test_size_limit(seeded, app, client):
    app.state.settings.max_image_bytes = 20_000
    big = io.BytesIO()
    Image.effect_noise((300, 300), 100).convert("RGB").save(big, "PNG")
    assert scan(client, big.getvalue(), "big.png", "image/png").status_code == 413


def test_scanned_file_is_deleted_and_never_posted(seeded_client, seeded, monkeypatch, tmp_path):
    from app.media import pipeline

    workdirs = []
    real_new = pipeline.new_workdir

    def tracking_workdir():
        path = real_new()
        workdirs.append(path)
        return path

    monkeypatch.setattr(pipeline, "new_workdir", tracking_workdir)
    uploads_before = set(Path(seeded.upload_dir).iterdir())
    feed_before = len(seeded_client.get("/api/v1/posts", headers=as_user(KOBE)).json()["items"])

    assert scan(seeded_client, make_jpeg()).status_code == 200
    assert workdirs and not any(w.exists() for w in workdirs)  # temp copy removed
    assert set(Path(seeded.upload_dir).iterdir()) == uploads_before  # nothing stored
    assert len(seeded_client.get("/api/v1/posts", headers=as_user(KOBE)).json()["items"]) == feed_before


def test_file_is_deleted_even_when_a_detector_crashes(seeded, app, client, monkeypatch):
    from app.media import pipeline

    workdirs = []
    real_new = pipeline.new_workdir
    monkeypatch.setattr(pipeline, "new_workdir", lambda: workdirs.append(real_new()) or workdirs[-1])

    class Boom(Detector):
        name, label, media_types = "boom", "Boom", frozenset({"image"})

        def analyze(self, media):
            raise RuntimeError("detector bug")

    setup = app.state.scanner
    app.state.scanner = registry.ScannerSetup(
        detectors=setup.detectors + (registry.ConfiguredDetector(Boom({}, seeded), 1.0),), combine=setup.combine
    )
    r = scan(client, make_jpeg())
    assert r.status_code == 200
    assert signal(r.json(), "boom")["status"] == "error"
    assert workdirs and not any(w.exists() for w in workdirs)


def test_scan_makes_no_network_connections(seeded_client, monkeypatch):
    """Detection is local: no detector may open a socket (e.g. to fetch a remote C2PA manifest)."""
    def refuse(*args, **kwargs):
        raise AssertionError("network access during scan")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    for name in ("AIoasis.jpg", "Phoenix_Sun.jpg"):
        assert scan(seeded_client, (SEED_MEDIA / name).read_bytes()).status_code == 200


def test_scanning_requires_sign_in(seeded_client):
    r = seeded_client.post(URL, files={"file": ("a.jpg", make_jpeg(), "image/jpeg")}, headers={"Origin": FRONTEND_ORIGIN})
    assert r.status_code == 401


def test_scan_rate_limit_is_per_user(seeded, app, client):
    app.state.settings.rate_limit_scans_per_hour = 2
    assert scan(client, make_jpeg()).status_code == 200
    assert scan(client, make_jpeg()).status_code == 200
    r = scan(client, make_jpeg())
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert scan(client, make_jpeg(), user=KARA).status_code == 200


# --- Combination rules ------------------------------------------------------------------

CFG = CombineConfig(min_conclusive_weight=1.0, ai_threshold=0.65, real_threshold=0.35)


def test_combine_inconclusive_when_nothing_is_conclusive():
    results = [(1.0, DetectorResult(score=0.9, confidence=1.0, explanation=""))]
    assert combine(results, CFG).verdict == "inconclusive"
    assert combine(results, CFG).score is None


def test_combine_middle_score_is_inconclusive():
    results = [
        (2.0, DetectorResult(score=0.9, confidence=1.0, conclusive=True, explanation="")),
        (2.0, DetectorResult(score=0.1, confidence=1.0, conclusive=True, explanation="")),
    ]
    assert combine(results, CFG).verdict == "inconclusive"


def test_combine_weighted_average_and_no_signal_is_ignored():
    results = [
        (3.0, DetectorResult(score=0.2, confidence=1.0, conclusive=True, explanation="")),
        (1.0, DetectorResult(score=0.6, confidence=0.5, explanation="")),
        (5.0, DetectorResult.no_signal("nothing")),  # left out, not counted as 0.5
    ]
    combined = combine(results, CFG)
    assert combined.score == pytest.approx((3 * 0.2 + 0.5 * 0.6) / 3.5)
    assert combined.verdict == "likely_real"


def test_combine_decisive_overrides_weak_signals():
    results = [
        (5.0, DetectorResult(score=0.99, confidence=1.0, conclusive=True, decisive=True, explanation="")),
        (10.0, DetectorResult(score=0.1, confidence=1.0, conclusive=True, explanation="")),
    ]
    combined = combine(results, CFG)
    assert combined.verdict == "likely_ai" and combined.score == pytest.approx(0.99)


# --- Detector measurements on synthetic input ------------------------------------------------

def _gradient(size=600):
    return np.tile(np.linspace(0, 255, size, dtype=np.float32), (size, 1))


def test_fft_finds_a_repeating_grid():
    plain = _gradient()
    pattern = np.sin(np.arange(600) * 2 * np.pi / 3).astype(np.float32)
    gridded = plain + 3 * pattern[None, :] * pattern[:, None]
    assert periodic_peak_z(plain, block_coded=False) < 12
    assert periodic_peak_z(gridded, block_coded=False) > 25


def test_noise_tells_clean_from_sensor_like():
    rng = np.random.default_rng(0)
    clean = _gradient()
    sensor = np.clip(clean + rng.normal(0, 1, clean.shape) * np.sqrt(clean / 10 + 1), 0, 255).astype(np.float32)
    assert noise_stats(clean).flat_sigma < 0.35
    stats = noise_stats(sensor)
    assert stats.flat_sigma > 1.0 and stats.brightness_corr > 0.3


def test_optical_flow_explains_motion_but_not_flicker():
    rng = np.random.default_rng(1)
    texture = (rng.random((240, 320)) * 255).astype(np.uint8)
    import cv2

    texture = cv2.GaussianBlur(texture, (0, 0), 3)
    shifted = np.roll(texture, 2, axis=1)  # the whole scene moves 2 px: fully explained by motion
    flicker = np.clip(texture.astype(np.int16) + rng.integers(-30, 30, texture.shape), 0, 255).astype(np.uint8)
    assert unexplained_change(texture, shifted) < 0.3
    assert unexplained_change(texture, flicker) > 0.6


# --- Registry: on/off flags and the off-device safety rule ----------------------------------

class FakeCloudDetector(Detector):
    name, label, media_types = "fakecloud", "Fake cloud API", frozenset({"image"})
    sends_media_off_device = True
    api_key_env = "FAKECLOUD_API_KEY"

    def analyze(self, media):
        return DetectorResult.no_signal("")


@pytest.fixture
def with_cloud_detector(monkeypatch):
    monkeypatch.setattr(registry, "DETECTOR_CLASSES", registry.DETECTOR_CLASSES + (FakeCloudDetector,))


def _names(setup):
    return {c.detector.name for c in setup.detectors}


def test_off_device_detector_is_off_without_explicit_enable(settings, with_cloud_detector, monkeypatch):
    monkeypatch.setenv("FAKECLOUD_API_KEY", "k")
    assert "fakecloud" not in _names(registry.build(settings, {"detectors": {}}))


def test_off_device_detector_fails_safe_without_api_key(settings, with_cloud_detector, monkeypatch):
    monkeypatch.delenv("FAKECLOUD_API_KEY", raising=False)
    config = {"detectors": {"fakecloud": {"enabled": True, "weight": 1.0}}}
    assert "fakecloud" not in _names(registry.build(settings, config))


def test_off_device_detector_runs_with_enable_and_key(settings, with_cloud_detector, monkeypatch):
    monkeypatch.setenv("FAKECLOUD_API_KEY", "k")
    config = {"detectors": {"fakecloud": {"enabled": True, "weight": 1.0}}}
    assert "fakecloud" in _names(registry.build(settings, config))


def test_config_flags_and_weights(settings):
    setup = registry.build(settings)  # the real scanner.toml
    names = _names(setup)
    assert {"c2pa", "metadata", "frequency", "noise", "ela", "video_frames", "temporal", "video_container"} <= names
    assert "face_swap" not in names  # off by default
    weights = {c.detector.name: c.weight for c in setup.detectors}
    assert weights["c2pa"] > weights["frequency"]
    off = registry.build(settings, {"detectors": {"c2pa": {"enabled": False, "weight": 5}}})
    assert _names(off) == set()


def test_enabled_face_swap_without_model_reports_unavailable(seeded, app, client):
    config = registry.load_config()
    config["detectors"]["face_swap"]["enabled"] = True
    app.state.scanner = registry.build(app.state.settings, config)
    body = scan(client, (SEED_MEDIA / "real-video-1.mp4").read_bytes(), "v.mp4", "video/mp4").json()
    face = signal(body, "face_swap")
    assert face["status"] == "unavailable" and "DEEPFAKE_MODEL_PATH" in face["explanation"]
