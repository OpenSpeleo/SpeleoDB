# -*- coding: utf-8 -*-

from __future__ import annotations

import binascii
import calendar
import contextlib
import datetime
import logging
import os
import pathlib
import time
from abc import ABCMeta
from abc import abstractmethod
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Self
from typing import override

import git
from django.conf import settings
from django.utils import timezone
from git import HEAD
from git import Blob
from git import Commit
from git import Repo
from git import Tree
from git.exc import GitCommandError
from git.exc import InvalidGitRepositoryError

from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.exceptions import GitBlobNotFoundError
from speleodb.git_engine.exceptions import GitPathNotFoundError

if TYPE_CHECKING:
    from collections.abc import Generator

    from git.types import Commit_ish

GIT_COMMITTER = git.Actor(
    settings.DJANGO_GIT_COMMITTER_NAME,
    settings.DJANGO_GIT_COMMITTER_EMAIL,
)

logger = logging.getLogger(__name__)

type PathLike = str | os.PathLike[str]

# class GitBlob(Blob):
#     def __init__(
#         self,
#         repo: Repo,
#         binsha: bytes,
#         mode: None | int = None,
#         path: None | str | pathlib.PathLike[str] = None,
#     ) -> None:
#         super().__init__(repo, binsha, mode, path)


# class GitDiff(Diff):
#     def __init__(
#         self,
#         repo: Repo,
#         a_rawpath: bytes | None,
#         b_rawpath: bytes | None,
#         a_blob_id: str | bytes | None,
#         b_blob_id: str | bytes | None,
#         a_mode: bytes | str | None,
#         b_mode: bytes | str | None,
#         new_file: bool,
#         deleted_file: bool,
#         copied_file: bool,
#         raw_rename_from: bytes | None,
#         raw_rename_to: bytes | None,
#         diff: str | bytes | None,
#         change_type: Literal["A", "D", "C", "M", "R", "T", "U"] | None,
#         score: int | None,
#     ) -> None:
#         super().__init__(
#             repo,
#             a_rawpath,
#             b_rawpath,
#             a_blob_id,
#             b_blob_id,
#             a_mode,
#             b_mode,
#             new_file,
#             deleted_file,
#             copied_file,
#             raw_rename_from,
#             raw_rename_to,
#             diff,
#             change_type,
#             score,
#         )


class GitObjectMixin(metaclass=ABCMeta):
    repo: GitRepo

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.abspath}>"

    @property
    def abspath(self) -> PathLike:
        raise NotImplementedError

    @property
    def commit(self) -> GitCommit:
        for commit in self.repo.iter_commits(all=True, paths=self.path):
            with contextlib.suppress(KeyError):
                item_path = str(self.path.parent).lstrip(".")
                file_or_tree: GitTree | GitFile = (
                    (commit.tree / item_path) if item_path else commit.tree
                )

                match file_or_tree:
                    case GitFile():
                        if self.binsha == file_or_tree.binsha:
                            return commit
                    case GitTree():
                        if self.binsha in file_or_tree.binshas:
                            return commit
                    case _:
                        raise TypeError(
                            "Expected GitFile or GitTree - Received: "
                            f"{type(file_or_tree)=}"
                        )

        raise FileNotFoundError

    @property
    @abstractmethod
    def binsha(self) -> bytes:
        raise NotImplementedError

    @property
    def hexsha(self) -> str:
        """:return: 40 byte hex version of our 20 byte binary sha"""
        return binascii.b2a_hex(self.binsha).decode("ascii")

    @property
    @abstractmethod
    def path(self) -> pathlib.Path:
        raise NotImplementedError


class GitFile(GitObjectMixin):
    def __init__(self, blob: Blob, repo: GitRepo) -> None:
        self._blob = blob.blob if isinstance(blob, GitFile) else blob
        self._repo = GitRepo.from_repo(repo) if not isinstance(repo, GitRepo) else repo

    @classmethod
    def from_hexsha(cls, repo: GitRepo, hexsha: str) -> GitFile:
        return repo.find_blob(hexsha)

    @property
    def repo(self) -> GitRepo:
        if not isinstance(self._repo, GitRepo):
            return GitRepo.from_repo(self._repo)
        return self._repo

    @repo.setter
    def repo(self, value: GitRepo | Repo) -> None:
        if not isinstance(value, GitRepo):
            value = GitRepo.from_repo(value)
        self._repo = value

    @property
    def blob(self) -> Blob:
        return self._blob

    @property
    def content(self) -> BytesIO:
        data = BytesIO(self.blob.data_stream.read())  # type: ignore[no-untyped-call]
        data.name = self.name
        return data

    @property
    def name(self) -> str:
        return self.blob.name

    @property
    def abspath(self) -> PathLike:
        return self.blob.abspath

    @property
    def path(self) -> pathlib.Path:
        return pathlib.Path(self.blob.path)

    @property
    def mode(self) -> int:
        # Octal File Permission Representation
        # Can be converted to actual file permission using:
        # >>> import stat
        # >>> stat.filemode(mode)
        return self.blob.mode

    @property
    def size(self) -> int:
        return self.blob.size

    @property
    def type(self) -> str:
        return self.blob.type

    @property
    def binsha(self) -> bytes:
        return self.blob.binsha


class GitDir(GitObjectMixin):
    def __init__(self, tree: Tree | GitTree, parent: Self | None = None) -> None:
        self._tree = tree if isinstance(tree, GitTree) else GitTree.from_tree(tree)
        self._parent = parent

    @property
    def tree(self) -> GitTree:
        return self._tree

    @property
    def path(self) -> pathlib.Path:
        return self.tree.path

    @property
    def parent(self) -> Self | None:
        return self._parent

    @property
    def files(self) -> Generator[GitFile]:
        for blob in self.tree.blobs:
            yield GitFile(repo=self.tree.repo, blob=blob)

    @property
    def root_files(self) -> Generator[GitFile]:
        for blob in self.tree.blobs:
            if str(Path(blob.path).parent) == ".":
                yield GitFile(repo=self.tree.repo, blob=blob)

    @property
    def subdirs(self) -> Generator[GitDir]:
        for sub_tree in self.tree.trees:
            yield GitDir(sub_tree)

    @property
    def binsha(self) -> bytes:
        return self.tree.binsha


class GitTree(Tree, GitObjectMixin):
    @classmethod
    def from_tree(cls, tree: Tree) -> Self:
        if not isinstance(tree, Tree):
            return TypeError(f"Expected `git.Tree` type, received: {type(tree)}")

        return cls(repo=tree.repo, binsha=tree.binsha, mode=tree.mode, path=tree.path)

    @property
    def repo(self) -> GitRepo:
        if not isinstance(self._repo, GitRepo):
            return GitRepo.from_repo(self._repo)
        return self._repo

    @repo.setter
    def repo(self, value: Repo | GitRepo) -> None:
        if not isinstance(value, GitRepo):
            value = GitRepo.from_repo(value)
        self._repo = value

    @property
    def path(self) -> pathlib.Path:
        return self._path

    @path.setter
    def path(self, value: PathLike) -> None:
        self._path = pathlib.Path(value)

    def _cast_to_type(self, item: Any) -> GitTree | GitFile | Any:
        match item:
            case Tree():
                return GitTree.from_tree(item)
            case GitTree():
                return item
            case Blob():
                return GitFile(repo=self.repo, blob=item)
            case GitFile():
                return item
            case _:
                return item

    def __truediv__(self, path: str | pathlib.Path) -> GitTree | GitFile | Any:  # type: ignore[override]
        """
        Overload the '/' operator to support custom path traversal.
        Special handling for '/' as the root.
        """
        path = str(path) if isinstance(path, pathlib.Path) else path
        return self._cast_to_type(super().__truediv__(path))

    def _iter_convert_to_object(  # type: ignore[override]
        self, iterable: list[Any]
    ) -> Generator[GitTree | GitFile | Any]:
        """Iterable yields tuples of (binsha, mode, name), which will be converted to
        the respective object representation.
        """
        for item in super()._iter_convert_to_object(iterable=iterable):
            yield self._cast_to_type(item)

    def __getitem__(self, item: Blob | Tree | Any) -> GitFile | GitTree | Any:  # type: ignore[override]
        return self._cast_to_type(super().__getitem__(item))  # type: ignore[index]

    @property
    def root(self) -> Generator[GitDir | GitFile]:
        """Retreive the root tree"""
        for sub_tree in self.trees:
            yield GitDir(sub_tree)

        for blob in self.blobs:
            yield GitFile(repo=self.repo, blob=blob)

    def get_file(self, path: pathlib.Path) -> GitFile:
        try:
            match obj := self[str(path)]:
                case GitFile():
                    return obj
                case Blob():
                    return GitFile(repo=self.repo, blob=obj)
                case _:
                    raise TypeError(f"Unsupported type received: {type(obj)=}")

        except KeyError as e:
            raise GitPathNotFoundError(f"Path: {path} not found") from e

    def __get_tree_files__(
        self, tree: GitTree, recursive: bool = True
    ) -> Generator[GitFile]:
        for blob in tree.blobs:
            yield GitFile(repo=self.repo, blob=blob)

        if recursive:
            for subtree in tree.trees:
                yield from self.__get_tree_files__(subtree, recursive=True)

    @property
    def trees(self) -> list[GitTree]:  # type: ignore[override]
        return [GitTree.from_tree(tree) for tree in super().trees]

    @property
    def files(self) -> Generator[GitFile]:
        """Retrieve all files in the tree
        Return:
            return a GitFile list
        """
        yield from self.__get_tree_files__(self, recursive=True)

    @property
    def root_files(self) -> Generator[GitFile]:
        """Retrieve all files in the tree
        Return:
            return a GitFile list
        """
        yield from self.__get_tree_files__(self, recursive=False)

    @property
    def binshas(self) -> Generator[bytes]:
        for item in self:
            yield item.binsha

        for subtree in self.trees:
            yield from subtree.binshas

    @property
    def binsha(self) -> bytes:
        return self._binsha

    @binsha.setter
    def binsha(self, value: bytes) -> None:
        self._binsha = value

    def traverse(self, *args: Any, **kwargs: Any) -> Generator[GitFile, GitTree]:  # type: ignore[override]
        yield from super().traverse(*args, **kwargs)  # type: ignore[misc]

    def scandir(self) -> Generator[GitFile, GitTree]:
        yield from self  # type: ignore[misc]


class GitCommit(Commit):
    """Represent A single Commit"""

    def __repr__(self) -> str:
        """:return: String with pythonic representation of our object"""
        return f"<{self.__class__.__name__}: {self.hexsha}>"

    @property
    def date(self) -> time.struct_time:
        return time.gmtime(self.committed_date)

    @property
    def date_dt(self) -> datetime.datetime:
        epoch_seconds = calendar.timegm(self.date)
        return datetime.datetime.fromtimestamp(
            epoch_seconds, tz=timezone.get_current_timezone()
        )

    @property
    def hexsha_short(self) -> str:
        """
        Returns the short version of the commit hash (7 characters by GitHub standard).
        """
        return self.hexsha[:7]

    @property
    def repo(self) -> GitRepo:
        # if not isinstance(self._repo, GitRepo):
        #     self._repo = GitRepo.from_repo(self._repo)
        return self._repo

    @repo.setter
    def repo(self, repo: Repo | GitRepo) -> None:
        self._repo = repo if isinstance(repo, GitRepo) else GitRepo.from_repo(repo)

    @property
    def changes(self) -> Generator[git.Diff]:
        """Retrieve the tree changes from parents"""

        with contextlib.suppress(IndexError):
            pc = self.repo.commit(self.parents[0])
            yield from pc.diff(other=self)

        for git_f in self.tree.files:
            yield git.Diff(
                repo=self.repo,
                a_rawpath=None,
                b_rawpath=str(git_f.blob.path).encode(),
                a_blob_id=None,
                b_blob_id=git_f.blob.hexsha,
                a_mode=None,
                b_mode=str(git_f.blob.mode),
                new_file=True,
                deleted_file=False,
                copied_file=False,
                raw_rename_from=None,
                raw_rename_to=None,
                diff="",
                change_type=None,
                score=None,
            )

    @property
    def tree(self) -> GitTree:
        if isinstance(self._tree, GitTree):
            return self._tree
        return GitTree.from_tree(self._tree)

    @tree.setter
    def tree(self, value: Tree | GitTree) -> None:
        if not isinstance(value, GitTree):
            value = GitTree.from_tree(value)
        self._tree = value

    @property
    def tags(self) -> list[str]:
        return [tag.name for tag in self.repo.tags if tag.commit.hexsha == self.hexsha]

    @property
    def branches(self) -> list[str]:
        return [
            branch_name
            for branch_name, hexsha in self.repo.branches.items()
            if hexsha == self.hexsha
        ]

    @property
    def files(self) -> Generator[GitFile]:
        yield from self.tree.files

    @property
    def root_files(self) -> Generator[GitFile]:
        """Retrieve all files in the root of the tree
        Return:
            return a GitFile list
        """
        yield from self.tree.root_files

    def tree_to_json(self, prefi: str = "") -> list[dict[str, Any]]:
        """Convert the commit tree to a JSON-serializable dictionary.

        Equivalent to:
        `git ls-tree -r HEAD | awk '{print "{\"mode\":\""$1"\", \"type\":\""$2"\", \"object\":\""$3"\", \"path\":\""$4"\"}"}' | jq -s .`
        """  # noqa: E501
        entries: list[dict[str, Any]] = []

        stack: list[tuple[GitTree | Tree, str]] = [
            (self.tree, "")
        ]  # (tree_object, path_prefix)

        for _ in range(int(1e6)):  # Safety limit to prevent infinite recursion
            if not stack:
                break

            tree, prefix = stack.pop()

            for item in tree:
                full_path = f"{prefix}/{item.name}".lstrip("/")

                # For subtrees, recurse
                match item:
                    case GitTree() | Tree():
                        # Behave like "git ls-tree -r": push subtree to stack
                        stack.append((item, full_path))

                    case GitFile() | Blob():
                        entries.append(
                            {
                                # octal like git ls-tree
                                "mode": format(item.mode, "o").zfill(6),
                                "type": item.type,
                                "object": item.hexsha,
                                "path": full_path,
                            }
                        )

                    case _:
                        raise ValueError(f"Unknown git object type: {item.type}")

        return entries


class GitHead(HEAD):
    @property  # type: ignore[misc]
    def commit(self) -> GitCommit:  # type: ignore[override]
        return GitCommit(repo=self.repo, binsha=super().commit.binsha)


class GitRepo(Repo):
    def __repr__(self) -> str:
        """:return: String with pythonic representation of our object"""
        return f"<{self.__class__.__name__}: {pathlib.Path(self.git_dir).parent}>"

    def __hash__(self) -> int:
        # Unique in `class`, absolute path, and git commit HEAD
        return hash((self.__class__, str(self.path.resolve()), self.head.commit.hexsha))

    @classmethod
    def from_directory(cls, directory: str | pathlib.Path) -> Self:
        if not isinstance(directory, pathlib.Path):
            directory = pathlib.Path(directory)

        if not directory.is_dir():
            directory.unlink(missing_ok=True)
            raise RuntimeError(f"The folder `{directory}` is not a folder.")

        try:
            return cls(directory)
        except InvalidGitRepositoryError as e:
            directory.rmdir()
            raise RuntimeError from e

    @classmethod
    def from_repo(cls, repo: Repo) -> Self:
        if not isinstance(repo, Repo):
            raise TypeError(f"Expected `Repo` type - Received: {type(repo)}")
        return cls(repo.working_dir)

    @classmethod
    def clone_from(cls, *args: Any, **kwargs: Any) -> Self:
        for _ in range(settings.DJANGO_GIT_RETRY_ATTEMPTS):
            repo = super().clone_from(*args, **kwargs)
            break
        else:
            try:
                url = kwargs["url"]
            except KeyError:
                url = args[0]

            raise GitBaseError(f"Impossible to clone repository: {url=}")

        return cls.from_repo(repo)

    @override
    def __eq__(self, other: GitRepo | Repo) -> bool:  # type: ignore[override]
        if not isinstance(other, (GitRepo, Repo)):
            return False

        if isinstance(other, Repo):
            other = GitRepo.from_repo(other)

        return self.path == other.path

    @property
    def path(self) -> pathlib.Path:
        return pathlib.Path(self.working_dir)

    @property
    def branches(self) -> dict[str, str]:  # type: ignore[override]
        return {ref.name: ref.commit.hexsha for ref in super().branches}

    @property  # type: ignore[misc]
    def description(self) -> str | None:  # type: ignore[override]
        try:
            return self.description
        except OSError:
            return None

    @override
    def commit(self, rev: Commit_ish | str | None = None) -> GitCommit:
        if rev is None:
            return self.head.commit
        """Retrieve a GitCommit object represent single commit from reporistory"""
        return GitCommit(repo=self, binsha=super().commit(rev).binsha)

    @property
    def commits(self) -> Generator[GitCommit]:
        for commit in self.get_commits():
            if commit.message != settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE:
                yield commit

    def get_commits(
        self,
        num: int | None = None,
        since: str | None = None,
        until: str | None = None,
        branch: str | None = None,
        path: str | Path | None = None,
    ) -> Generator[GitCommit]:
        """Retrieve the commits of repository
        Args:
            num: Number of commits to retrieve
            since: timestamp since retrieve commits
            until: timestamp until to retrieve commits
        Returns:
            A list of Commit object
        """
        params: dict[str, str | int] = {}
        if since:
            params["since"] = since

        if until:
            params["until"] = until

        if num:
            params["max_count"] = num

        yield from self.iter_commits(rev=branch, paths=path, **params)

    def iter_commits(self, *args: Any, **kwargs: Any) -> Generator[GitCommit]:
        for commit in super().iter_commits(*args, **kwargs):
            yield GitCommit(repo=self, binsha=commit.binsha)

    @property
    def commit_count(self) -> int:
        # Memoery efficient to compute the length of a generator
        return sum(
            1
            for commit in self.iter_commits()
            if commit.message != settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE
        )

    @property
    def tree(self) -> GitTree:  # type: ignore[override]
        return GitTree.from_tree(tree=super().tree())

    @property
    def head(self) -> GitHead:
        """
        :return:
            :class:`~git.refs.head.HEAD` object pointing to the current head reference
        """
        return GitHead(self, "HEAD")

    @classmethod
    def init(cls, path: pathlib.Path) -> Self:  # type: ignore[override]
        if path.exists():
            raise FileExistsError
        return cls.from_repo(super().init(path=path))

    def pull(self) -> None:
        origin = self.remotes.origin
        for _ in range(settings.DJANGO_GIT_RETRY_ATTEMPTS):
            with contextlib.suppress(GitCommandError):
                origin.pull("+refs/heads/*:refs/heads/*")
                break
        else:
            raise GitBaseError(
                "Impossible to pull repository: "
                f"{self.remotes.origin.url.split('@')[-1]}"  # Removes OAUTH2 token
            )

    def _checkout_branch_or_commit_and_maybe_pull(
        self, hexsha: str | None = None, branch_name: str | None = None
    ) -> None:
        if hexsha and branch_name:
            raise ValueError(
                f"`{hexsha=}` and `{branch_name=}` can not be set simultaneously."
            )

        if hexsha is None and branch_name is None:
            raise ValueError(
                f"`{hexsha=}` and `{branch_name=}` can not be both set to `None`."
            )

        if hexsha:
            with contextlib.suppress(GitCommandError):
                # Try to checkout the commit directly - no pull
                self.git.checkout(hexsha)
                return

        try:
            self.pull()
            self.git.checkout(branch_name or hexsha)

        except GitCommandError:
            if branch_name:  # Create the branch if it doesn't exist yet
                self.git.checkout("-b", branch_name)
            else:
                raise

    def checkout_default_branch_and_pull(self) -> None:
        try:
            self._checkout_branch_or_commit_and_maybe_pull(
                branch_name=settings.DJANGO_GIT_BRANCH_NAME
            )
        except GitBaseError:
            try:
                self.git.checkout("-b", settings.DJANGO_GIT_BRANCH_NAME)
            except GitCommandError:
                raise GitBaseError(
                    "Failed to checkout default branch and pull repository: "
                    f"{self.remotes.origin.url.split('@')[-1]}"
                ) from None

    def checkout_commit(self, hexsha: str) -> None:
        self._checkout_branch_or_commit_and_maybe_pull(hexsha=hexsha)

    def commit_and_push_project(
        self,
        message: str,
        author_name: str,
        author_email: str,
        force_empty_commit: bool = False,
    ) -> str | None:
        # Add every file pending
        self.index.add("*")

        # If there are modified files:
        if self.is_dirty() or force_empty_commit:
            author = git.Actor(author_name, author_email)

            commit = self.index.commit(message, author=author, committer=GIT_COMMITTER)

            for _ in range(settings.DJANGO_GIT_RETRY_ATTEMPTS):
                with contextlib.suppress(GitCommandError):
                    self.git.push("--set-upstream", "origin", self.active_branch)
                    break
            else:
                raise GitBaseError(
                    "Impossible to push to repository: "
                    f"{self.remotes.origin.url.split('@')[-1]}"  # Removes OAUTH2 token
                )

            return commit.hexsha

        return None

    def find_blob(self, hexsha: str) -> GitFile:
        for commit in self.iter_commits():
            for git_file in commit.tree.traverse():
                if git_file.hexsha == hexsha:
                    return git_file

        raise GitBlobNotFoundError(f"Git Object with id `{hexsha}` not found.")

    def reset_and_remove_untracked(self) -> None:
        # Step 1: Get the commit object to reset to
        target_commit = self.commit("HEAD")

        # Step 2: Reset HEAD to the target commit
        self.head.reference = target_commit
        self.head.reset(index=True, working_tree=True)

        # Step 3: Remove untracked files and directories manually
        # Get all untracked files and directories
        untracked_files = [self.path / path for path in self.untracked_files]
        maybe_untracked_dirs = [
            path.parent for path in untracked_files if path.parent != self.path
        ]

        # Delete untracked files
        for file_path in untracked_files:
            with contextlib.suppress(FileNotFoundError):
                file_path.unlink()

        # Delete untracked directories (if empty)
        # Reverse ensures inner directories are handled first
        for dir_path in sorted(maybe_untracked_dirs, reverse=True):
            with contextlib.suppress(OSError):
                dir_path.rmdir()

    def publish_first_commit(self) -> None:
        # Create an initial empty commit
        self.checkout_default_branch_and_pull()
        self.commit_and_push_project(
            settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE,
            author_name=settings.DJANGO_GIT_COMMITTER_NAME,
            author_email=settings.DJANGO_GIT_COMMITTER_EMAIL,
            force_empty_commit=True,
        )
