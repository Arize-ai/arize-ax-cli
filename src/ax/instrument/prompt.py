# ruff: noqa: TRY301
"""Resolve a signed onboarding prompt from the evals package."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from packaging.version import InvalidVersion, Version

from ax.core.exceptions import FileIOError
from ax.utils.http import unverified_ssl_context, verified_ssl_context

PROMPT_FILE_NAME = "onboarding-prompt.md"
_PACKAGE = "evals"
_TIMEOUT_SECONDS = 30
_MIN_PLAUSIBLE_BYTES = 4096
_MANIFEST_URLS = (
    f"https://cdn.jsdelivr.net/npm/{_PACKAGE}/prompt-manifest.json",
    f"https://unpkg.com/{_PACKAGE}/prompt-manifest.json",
)
ENV_PROMPT_MANIFEST_URL = "ARIZE_PROMPT_MANIFEST_URL"
_PUBLIC_KEYS_PEM = {
    "2026-09-17": b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA3JIYlN2pTEFodfsvMycv8nrmQhcyut25nEb8O3zM9kA=
-----END PUBLIC KEY-----
""",
    "2026-09-18": b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAilEU/i665pBdenk+mDYFlkCl6zYdW6wsqGT+WhPobRg=
-----END PUBLIC KEY-----
""",
}


@dataclass(frozen=True)
class PromptManifest:
    """Verified metadata for one immutable onboarding prompt."""

    prompt_url: str
    prompt_sha256: str
    minimum_ax_cli_version: str


def _manifest_urls() -> list[str]:
    """Return the signed manifest URL, with an explicit test override."""
    override = os.environ.get(ENV_PROMPT_MANIFEST_URL)
    return [override] if override else list(_MANIFEST_URLS)


def _fetch_bytes(url: str, *, verify: bool = True) -> bytes:
    """Download bytes from an HTTPS URL."""
    if not url.startswith("https://"):
        raise FileIOError(f"Refusing non-HTTPS onboarding URL: {url}")

    context = verified_ssl_context() if verify else unverified_ssl_context()
    try:
        with urllib.request.urlopen(  # noqa: S310 - URL is authenticated below
            url, timeout=_TIMEOUT_SECONDS, context=context
        ) as response:
            return response.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise FileIOError(f"Could not download {url}: {exc}") from exc


_SIGNED_FIELDS = {
    "key_id",
    "minimum_ax_cli_version",
    "prompt_sha256",
    "prompt_url",
    "revision",
    "schema_version",
}
_MANIFEST_FIELDS = _SIGNED_FIELDS | {"signature"}


def _signed_payload(metadata: dict[str, object]) -> bytes:
    """Return the canonical manifest payload covered by its signature."""
    return json.dumps(
        {key: metadata[key] for key in _SIGNED_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _parse_manifest(raw: bytes) -> PromptManifest:
    """Validate and authenticate a manifest downloaded from the CDN."""
    try:
        metadata = json.loads(raw)
        if (
            not isinstance(metadata, dict)
            or set(metadata) != _MANIFEST_FIELDS
            or metadata["schema_version"] != 1
        ):
            raise ValueError("unsupported schema version")
        signature = base64.b64decode(metadata["signature"], validate=True)
        key_id = str(metadata["key_id"])
        public_key = serialization.load_pem_public_key(_PUBLIC_KEYS_PEM[key_id])
        if not isinstance(public_key, Ed25519PublicKey):
            raise TypeError("embedded key is not Ed25519")
        public_key.verify(signature, _signed_payload(metadata))
        manifest = PromptManifest(
            prompt_url=str(metadata["prompt_url"]),
            prompt_sha256=str(metadata["prompt_sha256"]),
            minimum_ax_cli_version=str(metadata["minimum_ax_cli_version"]),
        )
        if len(manifest.prompt_sha256) != 64:
            raise ValueError("invalid prompt SHA-256")
        int(manifest.prompt_sha256, 16)
        if not manifest.prompt_url.startswith("https://"):
            raise ValueError("prompt URL must use HTTPS")
    except (InvalidSignature, KeyError, TypeError, ValueError) as exc:
        raise FileIOError(
            "Onboarding prompt manifest verification failed"
        ) from exc
    return manifest


def _is_compatible(manifest: PromptManifest) -> bool:
    """Return whether this CLI meets the prompt's minimum version."""
    from ax.version import __version__

    try:
        return Version(__version__) >= Version(manifest.minimum_ax_cli_version)
    except InvalidVersion as exc:
        raise FileIOError(
            "Onboarding prompt manifest has an invalid version"
        ) from exc


def resolve(*, verify: bool = True) -> str:
    """Download, authenticate, and return a compatible onboarding prompt."""
    errors: list[str] = []
    for url in _manifest_urls():
        try:
            manifest = _parse_manifest(_fetch_bytes(url, verify=verify))
            if not _is_compatible(manifest):
                raise FileIOError(
                    "This onboarding prompt requires a newer AX CLI "
                    f"({manifest.minimum_ax_cli_version} or later)"
                )
            raw = _fetch_bytes(manifest.prompt_url, verify=verify)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != manifest.prompt_sha256:
                raise FileIOError(
                    "Onboarding prompt digest verification failed"
                )
            if len(raw) < _MIN_PLAUSIBLE_BYTES:
                raise FileIOError("Onboarding prompt is too short")
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise FileIOError(
                    "Onboarding prompt is not valid UTF-8"
                ) from exc
        except FileIOError as exc:  # noqa: PERF203
            errors.append(str(exc))

    raise FileIOError(
        "Could not verify the onboarding prompt. Onboarding needs network "
        "access and an authenticated prompt.\n"
        + "\n".join(f"  {e}" for e in errors)
    )
