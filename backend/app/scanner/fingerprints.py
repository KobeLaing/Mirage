"""Text fingerprints that AI generators leave in file metadata.

Many generators write their name, or their settings, into the metadata they
save: EXIF "Software", XMP fields, PNG text chunks, MP4 encoder tags. Matching
whole words (not substrings) avoids false hits such as "flux" in "influx".
Only fairly specific names are listed; generic words like "runway" or
"playground" would match ordinary descriptions far too often.
"""

import re

GENERATOR_NAMES = (
    "midjourney", "stable diffusion", "stablediffusion", "sdxl", "dall-e", "dall·e", "dalle",
    "openai", "chatgpt", "gpt-4o", "sora", "firefly", "adobe firefly", "imagen", "gemini",
    "google generative ai", "synthid", "comfyui", "automatic1111", "novelai", "invokeai", "fooocus",
    "leonardo.ai", "ideogram", "black forest labs", "flux.1", "dreamstudio", "nightcafe",
    "bing image creator", "grok", "runwayml", "runway gen", "pika labs", "kling ai", "luma ai",
    "trainedalgorithmicmedia", "compositewithtrainedalgorithmicmedia", "ai generated", "ai-generated",
)

# Settings blocks that Stable Diffusion front-ends write into PNG text chunks.
SD_PARAMETER_HINTS = ("steps:", "sampler:", "cfg scale:", "seed:", "negative prompt:")

_PATTERN = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(n) for n in GENERATOR_NAMES) + r")(?![a-z0-9])")


def find_generators(text: str) -> list[str]:
    """Distinct generator names found in `text` (case-insensitive), in order of appearance."""
    seen: list[str] = []
    for match in _PATTERN.finditer(text.lower()):
        if match.group(1) not in seen:
            seen.append(match.group(1))
    return seen


def looks_like_sd_parameters(text: str) -> bool:
    lowered = text.lower()
    return sum(hint in lowered for hint in SD_PARAMETER_HINTS) >= 3
