from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ORGANIZATION = os.environ.get(
    "GITHUB_ORGANIZATION",
    "NASA-EarthRISE-DevelopersAcademy",
).strip()

API_TOKEN = os.environ.get("GITHUB_API_TOKEN", "").strip()

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPOSITORY_ROOT / "profile" / "README.md"

START_MARKER = "<!-- REPOSITORY_TABLE_START -->"
END_MARKER = "<!-- REPOSITORY_TABLE_END -->"

API_VERSION = "2022-11-28"
PER_PAGE = 100

EXCLUDED_REPOSITORIES = {
    ".github",
    ".github-private",
}


def fetch_repositories() -> list[dict[str, Any]]:
    """Return all organization repositories accessible to the API token."""

    if not ORGANIZATION:
        raise RuntimeError("GITHUB_ORGANIZATION is empty.")

    if not API_TOKEN:
        raise RuntimeError(
            "GITHUB_API_TOKEN is empty. Add the ORG_REPO_READ_TOKEN "
            "repository secret and pass it to this script in the workflow."
        )

    repositories: list[dict[str, Any]] = []
    page = 1

    while True:
        query = urllib.parse.urlencode(
            {
                "type": "all",
                "sort": "full_name",
                "direction": "asc",
                "per_page": PER_PAGE,
                "page": page,
            }
        )

        organization_path = urllib.parse.quote(
            ORGANIZATION,
            safe="",
        )

        url = (
            f"https://api.github.com/orgs/"
            f"{organization_path}/repos?{query}"
        )

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {API_TOKEN}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": (
                    f"{ORGANIZATION}-organization-profile-repository-list"
                ),
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:
                result = json.load(response)

        except urllib.error.HTTPError as error:
            response_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                "GitHub API request failed.\n"
                f"HTTP status: {error.code}\n"
                f"URL: {url}\n"
                f"Response: {response_body}"
            ) from error

        except urllib.error.URLError as error:
            raise RuntimeError(
                f"Unable to reach the GitHub API: {error.reason}"
            ) from error

        if not isinstance(result, list):
            raise RuntimeError(
                "GitHub returned an unexpected response instead of "
                "a repository list."
            )

        repositories.extend(result)

        if len(result) < PER_PAGE:
            break

        page += 1

    return repositories


def escape_markdown_table_cell(value: object) -> str:
    """Return text safe for use in a Markdown table cell."""

    text = "" if value is None else str(value)

    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = text.replace("|", r"\|")

    return " ".join(text.split()).strip()


def build_repository_table(
    repositories: list[dict[str, Any]],
) -> str:
    """Generate a Markdown table from organization repositories."""

    included_repositories = [
        repository
        for repository in repositories
        if str(repository.get("name", ""))
        not in EXCLUDED_REPOSITORIES
    ]

    included_repositories.sort(
        key=lambda repository: str(
            repository.get("name", "")
        ).casefold()
    )

    if not included_repositories:
        return "_No organization project repositories were found._"

    lines = [
        "| Repository | Description |",
        "|---|---|",
    ]

    for repository in included_repositories:
        name = escape_markdown_table_cell(
            repository.get("name", "Unnamed repository")
        )

        html_url = str(
            repository.get("html_url", "")
        ).strip()

        description = escape_markdown_table_cell(
            repository.get("description")
            or "No description provided."
        )

        status_labels: list[str] = []

        if repository.get("archived"):
            status_labels.append("Archived")

        if repository.get("disabled"):
            status_labels.append("Disabled")

        if status_labels:
            status_text = ", ".join(status_labels)
            description = f"{description} **{status_text}.**"

        repository_link = f"[{name}]({html_url})"

        lines.append(
            f"| {repository_link} | {description} |"
        )

    return "\n".join(lines)


def update_readme(repository_table: str) -> bool:
    """Replace the generated repository-table section in the README."""

    if not README_PATH.exists():
        raise FileNotFoundError(
            "Organization profile README was not found at "
            f"{README_PATH}."
        )

    current_content = README_PATH.read_text(
        encoding="utf-8"
    )

    start_count = current_content.count(START_MARKER)
    end_count = current_content.count(END_MARKER)

    if start_count != 1 or end_count != 1:
        raise RuntimeError(
            "profile/README.md must contain exactly one copy of each "
            "repository-table marker:\n"
            f"{START_MARKER}\n"
            f"{END_MARKER}"
        )

    start_position = current_content.index(START_MARKER)
    end_position = current_content.index(END_MARKER)

    if end_position <= start_position:
        raise RuntimeError(
            "The repository-table end marker occurs before the "
            "start marker."
        )

    content_before_table = current_content[
        : start_position + len(START_MARKER)
    ]

    content_after_table = current_content[
        end_position:
    ]

    updated_content = (
        f"{content_before_table}\n\n"
        f"{repository_table}\n\n"
        f"{content_after_table}"
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
    repositories = fetch_repositories()
    repository_table = build_repository_table(
        repositories
    )

    readme_changed = update_readme(
        repository_table
    )

    included_count = sum(
        str(repository.get("name", ""))
        not in EXCLUDED_REPOSITORIES
        for repository in repositories
    )

    print(
        f"Organization: {ORGANIZATION}"
    )
    print(
        f"Repositories returned by GitHub: {len(repositories)}"
    )
    print(
        f"Repositories included in table: {included_count}"
    )

    if readme_changed:
        print("Updated profile/README.md.")
    else:
        print("profile/README.md was already current.")


if __name__ == "__main__":
    main()
