"""Content Credentials (C2PA) check, for images and videos.

C2PA is an open standard for signed provenance data embedded in a file. Tools
such as Google's image generators, Adobe Firefly and OpenAI attach a manifest
whose "actions" record how the file was made, using IPTC "digital source type"
codes. trainedAlgorithmicMedia, for example, means "created by a generative AI
model". The c2pa library reads the manifest and checks its cryptographic
signature.

How we score it:
- Signed manifest says AI-made: decisive, close to 100%. The maker of the
  file is telling us, and the signature shows the claim wasn't edited.
- AI claim but broken signature: still strong evidence (nobody forges an
  "AI-made" label to look *more* fake), but not decisive.
- Signed manifest says camera capture: leans real. We don't check the signer
  against a trust list, though, and anyone can sign a claim, so this is
  weighed, not trusted outright.
- No manifest: no signal either way. Most real *and* most AI files have none.

Network safety: a manifest can point to a remote URL. Fetching it would make
our server request a URL chosen by whoever uploaded the file (a server-side
request forgery risk). Remote fetching is switched off, and any manifest
that isn't embedded in the file itself is ignored.
"""

import json
import logging

from app.scanner.base import Detector, DetectorResult, MediaInput

log = logging.getLogger("mirage.scanner.c2pa")

# IPTC digital source types (https://cv.iptc.org/newscodes/digitalsourcetype/).
AI_SOURCE_TYPES = frozenset({
    "trainedAlgorithmicMedia",
    "compositeWithTrainedAlgorithmicMedia",
    "algorithmicMedia",
    "compositeSynthetic",
})
CAPTURE_SOURCE_TYPES = frozenset({"digitalCapture", "computationalCapture", "negativeFilm", "positiveFilm"})

SDK_SETTINGS = {"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False}}


def _source_types(manifest: dict) -> tuple[set[str], list[str]]:
    """Digital source type codes and action descriptions found in a manifest's actions."""
    types: set[str] = set()
    descriptions: list[str] = []
    for assertion in manifest.get("assertions", []):
        if not str(assertion.get("label", "")).startswith("c2pa.actions"):
            continue
        for action in (assertion.get("data") or {}).get("actions", []):
            source = str(action.get("digitalSourceType", ""))
            if source:
                types.add(source.rstrip("/").rsplit("/", 1)[-1])
            if action.get("description"):
                descriptions.append(str(action["description"])[:120])
    return types, descriptions


class C2paDetector(Detector):
    name = "c2pa"
    label = "Content Credentials (C2PA)"
    media_types = frozenset({"image", "video"})

    def unavailable_reason(self) -> str | None:
        try:
            import c2pa  # noqa: F401
        except ImportError:
            return "The c2pa library isn't installed."
        return None

    def analyze(self, media: MediaInput) -> DetectorResult:
        import c2pa

        context = c2pa.Context(settings=c2pa.Settings.from_dict(SDK_SETTINGS))
        try:
            with media.path.open("rb") as f:
                reader = c2pa.Reader.try_create(media.mime, f, None, context)
                if reader is None:
                    return DetectorResult.no_signal(
                        "No Content Credentials found. Most files don't have them, so this points neither way."
                    )
                if not reader.is_embedded() or reader.get_remote_url():
                    return DetectorResult.no_signal(
                        "The file points to Content Credentials stored online. For safety we don't fetch them."
                    )
                state = reader.get_validation_state()
                data = json.loads(reader.json())
        except Exception as exc:  # malformed manifests raise many error types
            log.info("c2pa.read_failed", extra={"error": type(exc).__name__})
            return DetectorResult.no_signal("The file has Content Credentials data, but it couldn't be read.")

        manifests = data.get("manifests", {})
        active = manifests.get(data.get("active_manifest", ""), {})
        types: set[str] = set()
        descriptions: list[str] = []
        for manifest in manifests.values():  # the active manifest and the ingredients it was made from
            t, d = _source_types(manifest)
            types |= t
            descriptions += d
        issuer = (active.get("signature_info") or {}).get("issuer") or "an unknown signer"
        signed_ok = state in ("Valid", "Trusted")
        detail = f" ({descriptions[0]})" if descriptions else ""

        if types & AI_SOURCE_TYPES:
            if signed_ok:
                return DetectorResult(
                    score=0.99, confidence=1.0, conclusive=True, decisive=True,
                    explanation=f"Signed Content Credentials from {issuer} say this was made with generative AI{detail}.",
                )
            return DetectorResult(
                score=0.85, confidence=0.7, conclusive=True,
                explanation=f"Content Credentials say this was made with generative AI{detail}, "
                            "but the signature doesn't verify (the file changed after it was signed).",
            )
        if types & CAPTURE_SOURCE_TYPES and signed_ok:
            return DetectorResult(
                score=0.1, confidence=0.6, conclusive=True,
                explanation=f"Signed Content Credentials from {issuer} say this was captured by a camera. "
                            "The signer isn't checked against a trust list, so this is weighed, not proof.",
            )
        return DetectorResult.no_signal("Content Credentials are present but don't say how the media was made.")
