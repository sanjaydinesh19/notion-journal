from __future__ import annotations

from datetime import date
from typing import Optional

from github import Github, GithubException, InputGitTreeElement
from rich.console import Console

console = Console()


class JournalBackup:
    def __init__(self, token: str, repo_name: str):
        g = Github(token)
        user = g.get_user()
        self.repo = user.get_repo(repo_name)
        self._ensure_readme()

    def _ensure_readme(self):
        """Create a README on first use so the repo has an initial commit."""
        try:
            self.repo.get_contents("README.md")
        except GithubException:
            try:
                self.repo.create_file(
                    "README.md",
                    "init: journal backup repo",
                    "# Journal Entries\n\nPrivate backup of my Notion voice journal.\n",
                )
            except GithubException:
                pass

    def commit(
        self,
        entry_date: date,
        daily_md: str,
        weekly_md: Optional[str] = None,
        monthly_md: Optional[str] = None,
    ):
        """Commit daily (and optionally weekly/monthly) files in one git commit."""
        week_num = entry_date.isocalendar()[1]
        files = {
            f"daily/{entry_date.isoformat()}.md": f"# Daily Journal — {entry_date}\n\n{daily_md}",
        }
        if weekly_md:
            files[f"weekly/{entry_date.year}-W{week_num:02d}.md"] = (
                f"# Weekly Reflection — {entry_date.year} Week {week_num}\n\n{weekly_md}"
            )
        if monthly_md:
            files[f"monthly/{entry_date.year}-{entry_date.month:02d}.md"] = (
                f"# Monthly Goals — {entry_date.strftime('%B %Y')}\n\n{monthly_md}"
            )

        try:
            ref = self.repo.get_git_ref("heads/main")
        except GithubException:
            try:
                ref = self.repo.get_git_ref("heads/master")
            except GithubException:
                console.print("[yellow]GitHub backup: no branch found, skipping.[/]")
                return

        base_sha = ref.object.sha
        base_tree = self.repo.get_git_commit(base_sha).tree

        tree_elements = []
        for path, content in files.items():
            blob = self.repo.create_git_blob(content, "utf-8")
            tree_elements.append(
                InputGitTreeElement(path=path, mode="100644", type="blob", sha=blob.sha)
            )

        new_tree = self.repo.create_git_tree(tree_elements, base_tree)
        new_commit = self.repo.create_git_commit(
            f"journal: {entry_date.isoformat()}",
            new_tree,
            [self.repo.get_git_commit(base_sha)],
        )
        ref.edit(new_commit.sha)
        console.print(f"[dim]GitHub backup committed: {entry_date.isoformat()}[/]")
