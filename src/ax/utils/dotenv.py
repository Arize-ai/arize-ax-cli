"""Utilities for safely updating dotenv files."""

import os
import re
import stat
import tempfile
from contextlib import suppress
from pathlib import Path

from ax.core.exceptions import FileIOError

_DOTENV_FILENAME = re.compile(r"^\.env(?:\.[A-Za-z0-9_-]+)*$")
_ENVRC_FILENAME = ".envrc"
_API_KEY_ASSIGNMENT = re.compile(
    r"^(?P<indent>[ \t]*)(?P<export>export[ \t]+)?"
    r"(?P<name>ARIZE_API_KEY[ \t]*=(?P<value_space>[ \t]*))"
    r"(?P<value>.*)$"
)


def _is_envrc(file_path: Path) -> bool:
    """Whether the target is a direnv ``.envrc`` file.

    direnv sources ``.envrc`` as a shell script, so assignments must be
    ``export``ed to enter the environment and values must be quoted so the
    shell treats them literally.
    """
    return file_path.name == _ENVRC_FILENAME


def _shell_single_quote(value: str) -> str:
    """Single-quote a value so a shell-sourced ``.envrc`` reads it literally."""
    return "'" + value.replace("'", "'\\''") + "'"


def validate_dotenv_path(path: str) -> Path:
    """Validate a dotenv output path before creating an API key.

    Args:
        path: Target dotenv file path.

    Returns:
        The validated target path.

    Raises:
        FileIOError: If the path is not a supported dotenv filename, is a
            symlink, or cannot be created in its parent directory.
    """
    file_path = Path(path)
    if not (_DOTENV_FILENAME.fullmatch(file_path.name) or _is_envrc(file_path)):
        raise FileIOError(
            "--env-file must use a dotenv filename such as .env or "
            ".env.local, or a direnv .envrc file."
        )
    if file_path.is_symlink():
        raise FileIOError(
            f"--env-file must not be a symlink; refusing to replace it: "
            f"{file_path}. Point --env-file at the real file instead."
        )
    if not file_path.parent.is_dir():
        raise FileIOError(
            f"Parent directory does not exist: {file_path.parent}"
        )
    if file_path.exists() and not file_path.is_file():
        raise FileIOError(f"Dotenv target is not a regular file: {file_path}")
    return file_path


def _split_inline_comment(
    value: str, leading_comment_space: str = ""
) -> tuple[str, str]:
    """Split a dotenv value from its inline comment, preserving whitespace."""
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote is not None:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "#" and (
            (index > 0 and value[index - 1] in " \t")
            or (index == 0 and leading_comment_space)
        ):
            if index == 0:
                return "", leading_comment_space + value
            value_part = value[:index]
            trailing = re.search(r"[ \t]*$", value_part)
            if trailing is None:
                return value, ""
            return value_part[: trailing.start()], value_part[
                trailing.start() :
            ] + value[index:]
    return value, ""


def _replacement_value(
    existing_value: str,
    api_key: str,
    envrc: bool = False,
    leading_comment_space: str = "",
) -> str:
    """Format an API key using the existing value's quote style and comment.

    For ``.envrc`` targets the value is always single-quoted so direnv's
    shell parser reads it literally, regardless of any pre-existing quote
    style. For plain dotenv files the existing quote style is preserved.
    """
    value, comment = _split_inline_comment(
        existing_value, leading_comment_space
    )
    trailing = re.search(r"[ \t]*$", value)
    if trailing is None:
        return (_shell_single_quote(api_key) if envrc else api_key) + comment
    value = value[: trailing.start()]
    stripped = value.strip()
    if envrc:
        replacement = _shell_single_quote(api_key)
    elif stripped.startswith("'"):
        replacement = f"'{api_key}'"
    elif stripped.startswith('"'):
        replacement = f'"{api_key}"'
    else:
        replacement = api_key
    return replacement + trailing.group() + comment


def _update_dotenv_content(
    content: str, api_key: str, envrc: bool = False
) -> str:
    """Replace or append ARIZE_API_KEY while preserving file formatting.

    For direnv ``.envrc`` targets (``envrc=True``) the assignment is
    ``export``ed and the value single-quoted so direnv exports the key
    literally; a replaced assignment that lacks ``export`` is upgraded. For
    plain dotenv files the existing formatting is preserved unchanged.
    """
    newline = "\r\n" if "\r\n" in content else "\n"
    lines = content.splitlines(keepends=True)
    found_assignment = False
    for index, line in enumerate(lines):
        line_body = line.rstrip("\r\n")
        line_ending = line[len(line_body) :]
        match = _API_KEY_ASSIGNMENT.fullmatch(line_body)
        if match is not None:
            export = match.group("export") or ""
            if envrc and not export:
                export = "export "
            lines[index] = (
                match.group("indent")
                + export
                + match.group("name")
                + _replacement_value(
                    match.group("value"),
                    api_key,
                    envrc,
                    match.group("value_space"),
                )
                + line_ending
            )
            found_assignment = True

    if found_assignment:
        return "".join(lines)

    if envrc:
        assignment = f"export ARIZE_API_KEY={_shell_single_quote(api_key)}"
    else:
        assignment = f"ARIZE_API_KEY={api_key}"
    if not content:
        return assignment + newline
    if content.endswith(("\n", "\r")):
        return content + assignment + newline
    return content + newline + assignment + newline


def write_api_key_to_dotenv(path: str, api_key: str) -> None:
    """Atomically write an API key to a dotenv file.

    Existing ``ARIZE_API_KEY`` assignments retain their export prefix, quote
    style, inline comments, and surrounding file content.

    Args:
        path: Target dotenv file path.
        api_key: Newly generated API key.

    Raises:
        FileIOError: If the file cannot be read or atomically written.
    """
    file_path = validate_dotenv_path(path)
    try:
        if file_path.exists():
            with file_path.open(encoding="utf-8", newline="") as dotenv_file:
                content = dotenv_file.read()
            mode = stat.S_IMODE(file_path.stat().st_mode)
        else:
            content = ""
            mode = None
        updated = _update_dotenv_content(
            content, api_key, envrc=_is_envrc(file_path)
        )

        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{file_path.name}.", dir=file_path.parent
        )
        try:
            with os.fdopen(
                descriptor, "w", encoding="utf-8", newline=""
            ) as temp:
                temp.write(updated)
                temp.flush()
                os.fsync(temp.fileno())
            if mode is not None:
                os.chmod(temporary_path, mode)
            os.replace(temporary_path, file_path)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary_path)
    except Exception as e:
        if isinstance(e, FileIOError):
            raise
        raise FileIOError(
            f"Failed to update dotenv file {file_path}: {e}"
        ) from e
