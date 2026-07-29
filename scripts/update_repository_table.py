from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ORGANIZATION = os.environ.get(
    "GITHUB_ORGANIZATION",
    "NASA-EarthRISE-DevelopersAcademy",
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPOSITORY_ROOT / "profile" / "README.md"

START_MARKER = "<!-- REPOSITORY_TABLE_START -->"
END_MARKER = "<!-- REPOSITORY_TABLE_END -->"

API_VERSION = "2026-03-10"
PER_PAGE = 100


def fetch_public_repositories() -> list[dict[str, Any]]:
    """Return every public repository in the organization."""

    repositories: list[dict[str, Any]] = []
    page = 1

    while True:
        query = urllib.parse.urlencode(
            {
                "type": "public",
                "sort": "full_name",
                "direction": "asc",
                "per_page": PER_PAGE,
                "page": page,
            }
        )

        url = (
            f"https://api.github.com/orgs/"
            f"{urllib.parse.quote(ORGANIZATION, safe='')}/repos?{query}"
        )

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": (
                    f"{ORGANIZATION}-organization-profile-repository-list"
                ),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            response_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API request failed with HTTP {error.code}: "
                f"{response_body}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                f"Unable to reach the GitHub API: {error.reason}"
            ) from error

        if not isinstance(result, list):
            raise RuntimeError(
                "GitHub API returned an unexpected response instead of "
                "a repository list."
            )

        repositories.extend(result)

        if len(result) < PER_PAGE:
            break

        page += 1

    return repositories


def escape_markdown_table_cell(value: object) -> str:
    """Escape text so it is safe inside a Markdown table cell."""

    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("|", r"\|")
    return " ".join(text.split()).strip()


def build_repository_table(
    repositories: list[dict[str, Any]],
) -> str:
    """Build the Markdown table, excluding the .github repository."""

    included_repositories = [
        repository
        for repository in repositories
        if repository.get("name") != ".github"
    ]

    included_repositories.sort(
        key=lambda repository: str(
            repository.get("name", "")
        ).casefold()
    )

    if not included_repositories:
        return "_No public organization repositories were found._"

    lines = [
        "| Repository | Description |",
        "|---|---|",
    ]

    for repository in included_repositories:
        name = escape_markdown_table_cell(
            repository.get("name", "Unnamed repository")
        )
        html_url = str(repository.get("html_url", "")).strip()
        description = escape_markdown_table_cell(
            repository.get("description")
            or "No description provided."
        )

        if repository.get("archived"):
            description = f"{description} **Archived.**"

        repository_link = f"[{name}]({html_url})"
        lines.append(f"| {repository_link} | {description} |")

    return "\n".join(lines)


def update_readme(table: str) -> bool:
    """Replace the generated region and report whether the file changed."""

    if not README_PATH.exists():
        raise FileNotFoundError(
            f"Organization profile README not found: {README_PATH}"
        )

    current_content = README_PATH.read_text(encoding="utf-8")

    marker_pattern = re.compile(
        rf"{re.escape(START_MARKER)}"
        rf".*?"
        rf"{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )

    replacement = (
        f"{START_MARKER}\n\n"
        f"{table}\n\n"
        f"{END_MARKER}"
    )

    updated_content, replacement_count = marker_pattern.subn(
        replacement,
        current_content,
        count=1,
    )

    if replacement_count != 1:
        raise RuntimeError(
            "Could not find exactly one repository-table marker section "
            f"in {README_PATH}."
        )

    if updated_content == current_content:
        return False

    README_PATH.write_text(
        updated_content,
        encoding="utf-8",
        newline="\n",
    )
    return True


def main() -> None:
    repositories = fetch_public_repositories()
    table = build_repository_table(repositories)
    changed = update_readme(table)

    included_count = sum(
        repository.get("name") != ".github"
        for repository in repositories
    )

    print(
        f"Found {included_count} public repositories other than .github."
    )
    print(
        "Updated profile/README.md."
        if changed
        else "profile/README.md was already current."
    )


if __name__ == "__main__":
    main()
