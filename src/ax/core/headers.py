"""Built-in CLI identity headers sent on every Arize API request.

These mirror the SDK's own identity headers (``sdk-language``,
``language-version``, etc.) but identify the ``ax`` CLI specifically, so the
backend can distinguish CLI traffic from direct SDK usage. They are passed to
``SDKConfiguration.default_headers`` and the SDK merges them into every
transport (HTTP/REST, grpc-gateway, and Flight).
"""

import sys

from ax.version import __version__

CLI_LANGUAGE = "python"
CLI_PACKAGE_NAME = "arize-ax-cli"

_PYTHON_VERSION = (
    f"{sys.version_info.major}."
    f"{sys.version_info.minor}."
    f"{sys.version_info.micro}"
)


def cli_default_headers() -> dict[str, str]:
    """Return the CLI's identity headers.

    Returns:
        A mapping suitable for ``SDKConfiguration.default_headers`` identifying
        the CLI language, interpreter version, package name, and CLI version.
    """
    return {
        "cli-language": CLI_LANGUAGE,
        "cli-language-version": _PYTHON_VERSION,
        "cli-package-name": CLI_PACKAGE_NAME,
        "cli-version": __version__,
    }
