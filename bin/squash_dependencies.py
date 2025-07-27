#!/usr/bin/env python3

"""
Git History Dependency Squasher - Tree-Only Approach

This script rebuilds git history using ONLY git commit-tree and git reset.
No cherry-pick, no rebase, no interactive operations whatsoever.

For each commit, we create a new commit using git commit-tree with the
original tree, preserving all metadata. For dependency sequences, we
create a single commit using the tree from the last commit in the sequence.
"""

import os
import re
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Commit:
    hash: str
    message: str
    author_name: str
    author_email: str
    author_date: str
    committer_name: str
    committer_email: str
    committer_date: str
    tree_hash: str


class DependencySquasher:
    def __init__(self, base_branch: str = "master", target_branch: str = "rewrite"):
        self.base_branch = base_branch
        self.target_branch = target_branch
        self.dependency_patterns = [
            r"dependabot",
            r"bump\s+.*\s+from\s+.*\s+to\s+",
            r"bump python.*",
            r"dependency",
            r"dependencies",
            r"update.*dependencies",
            r"update.*from",
            r"updated to",
            r"merge.*dependabot",
            r"Bump\s+.*\s+from\s+.*\s+to\s+",
            r"^Merge\s+pull\s+request.*dependabot",
            r"^Merge\s+remote-tracking\s+branch.*dependabot",
        ]

    def run_git_command(self, cmd: list[str]) -> str:
        """Run a git command and return the output."""
        try:
            result = subprocess.run(
                ["git", *cmd],
                capture_output=True,
                text=True,
                check=True,
                cwd=os.getcwd(),
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"Git command failed: {' '.join(['git'] + cmd)}\nError: {e.stderr}"
            )

    def is_dependency_commit(self, commit: Commit) -> bool:
        """Check if a commit is dependency-related."""
        msg_lower = commit.message.lower()
        return any(
            re.search(pattern, msg_lower, flags=re.IGNORECASE)
            for pattern in self.dependency_patterns
        )

    def get_all_commits(self) -> list[Commit]:
        """Get all commits from base branch in chronological order (oldest first)."""
        print("Getting commit list...")

        # Get commit hashes in reverse order (oldest first)
        commit_hashes = self.run_git_command(
            ["rev-list", "--reverse", self.base_branch]
        ).split("\n")

        commits = []
        for i, commit_hash in enumerate(commit_hashes):
            if i % 50 == 0:
                print(f"Loading commit metadata: {i + 1}/{len(commit_hashes)}")

            # Get detailed commit info
            commit_info = self.run_git_command(
                [
                    "show",
                    "--format=%H%n%s%n%an%n%ae%n%ai%n%cn%n%ce%n%ci%n%T",
                    "--no-patch",
                    commit_hash,
                ]
            ).split("\n")

            commit = Commit(
                hash=commit_info[0],
                message=commit_info[1],
                author_name=commit_info[2],
                author_email=commit_info[3],
                author_date=commit_info[4],
                committer_name=commit_info[5],
                committer_email=commit_info[6],
                committer_date=commit_info[7],
                tree_hash=commit_info[8],
            )
            commits.append(commit)

        print(f"Loaded {len(commits)} commits")
        return commits

    def create_orphan_branch(self):
        """Create a fresh orphan branch for the rewrite."""
        print(f"Creating fresh orphan branch: {self.target_branch}")

        # Create orphan branch
        self.run_git_command(["checkout", "--orphan", self.target_branch])

        # Remove all files
        self.run_git_command(["rm", "-rf", "."])

        # Create initial empty commit using commit-tree
        empty_tree = self.run_git_command(["hash-object", "-t", "tree", "/dev/null"])
        empty_commit = self.create_commit_with_tree(
            tree_hash=empty_tree,
            parent_hash=None,
            message="Initial empty commit",
            author_name="Jonathan Dekhtiar",
            author_email="jonathan@dekhtiar.com",
            author_date="2024-04-28T00:00:00Z",
            committer_name="Jonathan Dekhtiar",
            committer_email="jonathan@dekhtiar.com",
            committer_date="2024-04-28T00:00:00Z",
        )

        # Move branch to point to this commit
        self.run_git_command(["reset", "--hard", empty_commit])
        print(f"✓ Created initial commit: {empty_commit[:8]}")

    def create_commit_with_tree(
        self,
        tree_hash: str,
        parent_hash: str | None,
        message: str,
        author_name: str,
        author_email: str,
        author_date: str,
        committer_name: str,
        committer_email: str,
        committer_date: str,
    ) -> str:
        """Create a commit using git commit-tree."""
        cmd = ["git", "commit-tree", tree_hash]
        if parent_hash:
            cmd.extend(["-p", parent_hash])
        cmd.extend(["-m", message])

        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_AUTHOR_DATE": author_date,
            "GIT_COMMITTER_NAME": committer_name,
            "GIT_COMMITTER_EMAIL": committer_email,
            "GIT_COMMITTER_DATE": committer_date,
        }

        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, env=env
        )
        if result.returncode != 0:
            raise Exception(f"Failed to create commit: {result.stderr}")

        return result.stdout.strip()

    def get_current_head(self) -> str:
        """Get the current HEAD commit hash."""
        return self.run_git_command(["rev-parse", "HEAD"])

    def apply_regular_commit(self, commit: Commit, parent_hash: str) -> str:
        """Apply a regular commit using commit-tree."""
        new_commit = self.create_commit_with_tree(
            tree_hash=commit.tree_hash,
            parent_hash=parent_hash,
            message=commit.message,
            author_name=commit.author_name,
            author_email=commit.author_email,
            author_date=commit.author_date,
            committer_name=commit.committer_name,
            committer_email=commit.committer_email,
            committer_date=commit.committer_date,
        )

        print(f"✓ Applied regular commit: {commit.message[:60]}...")
        return new_commit

    def apply_dependency_sequence(
        self, dependency_commits: list[Commit], parent_hash: str
    ) -> str:
        """Apply a sequence of dependency commits as a single squashed commit."""
        if not dependency_commits:
            return parent_hash

        first_commit = dependency_commits[0]
        last_commit = dependency_commits[-1]

        print(f"✓ Squashing {len(dependency_commits)} dependency commits into one")
        print(f"  First: {first_commit.message[:60]}...")
        print(f"  Last:  {last_commit.message[:60]}...")

        # Create a single commit using the tree from the last dependency commit
        # but with author date from the first commit
        new_commit = self.create_commit_with_tree(
            tree_hash=last_commit.tree_hash,
            parent_hash=parent_hash,
            message="Dependency Update",
            author_name="Jonathan Dekhtiar",
            author_email="jonathan@dekhtiar.com",
            author_date=first_commit.author_date,
            committer_name="Jonathan Dekhtiar",
            committer_email="jonathan@dekhtiar.com",
            committer_date=first_commit.committer_date,
        )

        print(f"  ✓ Created squashed dependency commit: {new_commit[:8]}")
        return new_commit

    def process_commits(self, commits: list[Commit]):
        """Process all commits, squashing consecutive dependency commits."""
        dependency_buffer = []
        processed = 0
        current_head = self.get_current_head()

        def flush_dependency_buffer():
            nonlocal current_head
            if dependency_buffer:
                new_commit = self.apply_dependency_sequence(
                    dependency_buffer, current_head
                )
                self.run_git_command(["reset", "--hard", new_commit])
                current_head = new_commit
                dependency_buffer.clear()

        for i, commit in enumerate(commits):
            processed += 1

            if processed % 10 == 0:
                print(f"Progress: {processed}/{len(commits)} commits processed")

            if self.is_dependency_commit(commit):
                # Add to dependency buffer
                dependency_buffer.append(commit)
                print(f"  📦 Buffering dependency commit: {commit.message[:60]}...")
            else:
                # Flush any pending dependency commits
                flush_dependency_buffer()

                # Apply this regular commit
                new_commit = self.apply_regular_commit(commit, current_head)
                self.run_git_command(["reset", "--hard", new_commit])
                current_head = new_commit

        # Flush any remaining dependency commits
        flush_dependency_buffer()

    def verify_final_state(self) -> bool:
        """Verify that the final state matches the original branch."""
        print("Verifying final repository state...")

        try:
            # Compare trees between master and rewrite
            master_tree = self.run_git_command(
                ["rev-parse", f"{self.base_branch}^{{tree}}"]
            )
            rewrite_tree = self.run_git_command(
                ["rev-parse", f"{self.target_branch}^{{tree}}"]
            )

            if master_tree == rewrite_tree:
                print("✅ Final state verification: PASSED")
                return True
            print("❌ Final state verification: FAILED")
            print(f"Master tree:  {master_tree}")
            print(f"Rewrite tree: {rewrite_tree}")
            return False

        except Exception as e:
            print(f"❌ Error during verification: {e}")
            return False

    def run(self):
        """Run the complete dependency squashing process."""
        print("=== Git History Dependency Squasher (Tree-Only Approach) ===")
        print(f"Base branch: {self.base_branch}")
        print(f"Target branch: {self.target_branch}")
        print("Using ONLY git commit-tree and git reset - no cherry-pick or rebase!")
        print()

        try:
            # Ensure we're on the base branch
            self.run_git_command(["checkout", self.base_branch])

            # Get all commits
            commits = self.get_all_commits()

            # Create fresh target branch
            self.create_orphan_branch()

            # Process all commits
            self.process_commits(commits)

            print(f"\n✅ Successfully processed {len(commits)} commits")

            # Verify final state
            if self.verify_final_state():
                print("\n🎉 Dependency squashing completed successfully!")
                print(
                    f"The '{self.target_branch}' branch now contains the squashed history."
                )
                print("Final repository state matches the original - no differences!")
            else:
                print(
                    "\n⚠️  Dependency squashing completed but final state doesn't match!"
                )
                print("You may want to investigate the differences.")

        except Exception as e:
            print(f"\n❌ Error during processing: {e}")
            sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Squash consecutive dependency commits in git history"
    )
    parser.add_argument(
        "--base", default="master", help="Base branch (default: master)"
    )
    parser.add_argument(
        "--target", default="rewrite", help="Target branch (default: rewrite)"
    )

    args = parser.parse_args()

    squasher = DependencySquasher(args.base, args.target)
    squasher.run()
