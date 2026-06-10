"""Tests for the CLI's built-in identity headers."""

import sys

from ax.core.headers import cli_default_headers
from ax.version import __version__


class TestCliDefaultHeaders:
    """Verify the identity headers sent on every Arize API request."""

    def test_emits_exactly_the_four_identity_headers(self) -> None:
        """The helper emits exactly the four documented cli-* headers.

        Asserting the whole dict pins the exact key set, the static literals,
        and that ``cli-version``/``cli-language-version`` are sourced from
        ``__version__`` and ``sys.version_info`` (not hardcoded), so the test
        does not drift when either bumps.
        """
        expected_language_version = (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )
        assert cli_default_headers() == {
            "cli-language": "python",
            "cli-language-version": expected_language_version,
            "cli-package-name": "arize-ax-cli",
            "cli-version": __version__,
        }
