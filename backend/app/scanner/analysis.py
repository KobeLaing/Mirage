"""Pixel statistics shared by the image detectors and the video frame detector.

All functions take a grayscale float32 array (0..255) and work on a centre
crop. They crop rather than resize because resizing blends neighbouring
pixels, and that would erase the fine pixel-level traces being measured.
"""

from dataclasses import dataclass

import cv2
import numpy as np

FFT_SIZE = 512
NOISE_SIZE = 1024
MIN_SIZE = 128
BLOCK = 16


def center_crop(gray: np.ndarray, size: int, multiple: int = 8) -> np.ndarray | None:
    h, w = gray.shape[:2]
    side = min(size, h, w)
    side -= side % multiple
    if side < MIN_SIZE:
        return None
    top, left = (h - side) // 2, (w - side) // 2
    return gray[top:top + side, left:left + side]


def periodic_peak_z(gray: np.ndarray, *, block_coded: bool) -> float | None:
    """How strongly the image's frequency spectrum has isolated, repeating peaks.

    Image generators build pictures by repeatedly upsampling small feature
    maps, which can leave a faint grid that repeats every few pixels. In the
    2-D Fourier transform, a pattern that repeats regularly shows up as sharp,
    isolated bright points instead of the smooth falloff of a natural photo.

    Steps: remove the smooth picture content (keep the fine detail), window it
    so the crop's edges don't add false lines, take the FFT, and measure how
    far the brightest points stand above their local surroundings. The answer
    is in robust standard deviations (a z-score).

    block_coded: JPEG and video codecs work in 8x8 blocks, which puts peaks at
    exactly the 1/8 grid of frequencies. Those positions are ignored, or every
    JPEG would look "AI-made".
    """
    crop = center_crop(gray, FFT_SIZE)
    if crop is None:
        return None
    s = crop.shape[0]
    detail = crop - cv2.GaussianBlur(crop, (0, 0), 1.0)
    window = np.outer(np.hanning(s), np.hanning(s)).astype(np.float32)
    spectrum = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(detail * window)))).astype(np.float32)
    peaks = spectrum - cv2.blur(spectrum, (9, 9))

    c = s // 2
    yy, xx = np.mgrid[0:s, 0:s]
    dy, dx = yy - c, xx - c
    mask = np.hypot(dy, dx) >= 0.08 * s  # skip the low frequencies (overall shapes and shading)
    mask &= (np.abs(dx) > 2) & (np.abs(dy) > 2)  # skip the axes (crop edges and straight lines)
    if block_coded:
        step = s / 8
        near_x = np.abs(dx / step - np.round(dx / step)) * step <= 2
        near_y = np.abs(dy / step - np.round(dy / step)) * step <= 2
        mask &= ~(near_x & near_y)

    values = peaks[mask]
    median = float(np.median(values))
    spread = float(np.median(np.abs(values - median))) * 1.4826 + 1e-6
    top = np.sort(values)[-8:]  # the brightest few points (peaks come in mirrored pairs)
    return float((top.mean() - median) / spread)


@dataclass(frozen=True)
class NoiseStats:
    flat_sigma: float  # typical noise level in smooth areas, in 0..255 grey levels
    brightness_corr: float  # does noise grow with brightness? (+1 = strongly)
    flat_blocks: int


def noise_stats(gray: np.ndarray) -> NoiseStats | None:
    """Measure the fine-grained noise in the smooth parts of the picture.

    A camera sensor adds random noise to every pixel, and because light
    arrives as individual photons, that noise is stronger in brighter areas
    ("shot noise"). Generators usually produce smooth areas that are either
    almost perfectly clean or carry noise unrelated to brightness.

    Steps: subtract a median-filtered copy to isolate the noise; split into
    16x16 blocks; keep the smoothest blocks (where noise isn't confused with
    real texture) and skip clipped black or white blocks; then measure the
    noise level there and how it correlates with brightness.
    """
    crop = center_crop(gray, NOISE_SIZE, multiple=BLOCK)
    if crop is None:
        return None
    crop = np.ascontiguousarray(crop, dtype=np.float32)
    residual = crop - cv2.medianBlur(crop, 3)
    gx = cv2.Sobel(cv2.GaussianBlur(crop, (0, 0), 2.0), cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(cv2.GaussianBlur(crop, (0, 0), 2.0), cv2.CV_32F, 0, 1)
    gradient = np.hypot(gx, gy)

    n = crop.shape[0] // BLOCK
    def blocks(a: np.ndarray) -> np.ndarray:
        return a[: n * BLOCK, : n * BLOCK].reshape(n, BLOCK, n, BLOCK).swapaxes(1, 2).reshape(-1, BLOCK * BLOCK)

    sigma = blocks(residual).std(axis=1)
    brightness = blocks(crop).mean(axis=1)
    texture = blocks(gradient).mean(axis=1)

    usable = (brightness > 15) & (brightness < 240)
    if usable.sum() < 20:
        return None
    flat = usable & (texture <= np.quantile(texture[usable], 0.3))
    if flat.sum() < 10:
        return None
    s, b = sigma[flat], brightness[flat]
    corr = float(np.corrcoef(b, s)[0, 1]) if s.std() > 1e-6 and b.std() > 1e-6 else 0.0
    return NoiseStats(flat_sigma=float(np.median(s)), brightness_corr=corr, flat_blocks=int(flat.sum()))
