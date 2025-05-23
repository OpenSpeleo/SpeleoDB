from __future__ import annotations

import binascii
import contextlib
import logging
import pathlib
import time
from abc import ABCMeta
from abc import abstractmethod
from io import BytesIO
from typing import TYPE_CHECKING
from typing import Any
from typing import Self
from typing import override

import git
from django.conf import settings
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
    from collections.abc import Iterator

    from git.objects.base import IndexObjUnion
    from git.objects.tree import TraversedTreeTup
    from git.types import Commit_ish

GIT_COMMITTER = git.Actor(
    settings.DJANGO_GIT_COMMITTER_NAME,
    settings.DJANGO_GIT_COMMITTER_EMAIL,
)

logger = logging.getLogger(__name__)

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
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.abspath}>"

    @property
    def commit(self):
        for commit in self.repo.iter_commits(all=True, paths=self.path):
            with contextlib.suppress(KeyError):
                item_path = str(self.path.parent).lstrip(".")
                tree = commit.tree / item_path if item_path else commit.tree
                if self.binsha in tree.binshas:
                    return commit
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
        self._blob = blob
        self._repo = repo
        self._repo = GitRepo.from_repo(repo) if not isinstance(repo, GitRepo) else repo

    @classmethod
    def from_hexsha(cls, repo: GitRepo, hexsha: str) -> Self:
        blob = repo.blob(hexsha)
        return cls(repo=repo, blob=blob)

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
        data = BytesIO(self.blob.data_stream.read())
        data.name = self.name
        return data

    @property
    def name(self) -> str:
        return self.blob.name

    @property
    def abspath(self) -> pathlib.Path:
        return pathlib.Path(self.blob.abspath)

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
            if blob.path.parent == ".":
                yield GitFile(repo=self.tree.repo, blob=blob)

    @property
    def subdirs(self) -> Generator[Self]:
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
    def path(self, value: str | pathlib.Path) -> None:
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

    @override
    def __truediv__(self, path: str | pathlib.Path) -> GitTree | GitFile | Any:
        """
        Overload the '/' operator to support custom path traversal.
        Special handling for '/' as the root.
        """
        path = str(path) if isinstance(path, pathlib.Path) else path
        return self._cast_to_type(super().__truediv__(path))

    def _iter_convert_to_object(
        self, iterable: list
    ) -> Generator[GitTree, GitFile, Any]:
        """Iterable yields tuples of (binsha, mode, name), which will be converted to
        the respective object representation.
        """
        for item in super()._iter_convert_to_object(iterable=iterable):
            yield self._cast_to_type(item)

    @override
    def __getitem__(self, item: Blob | Tree | Any) -> GitFile | GitTree | Any:
        return self._cast_to_type(super().__getitem__(item=item))

    @property
    def root(self) -> Generator[GitDir | GitFile]:
        """Retreive the root tree"""
        for sub_tree in self.trees:
            yield GitDir(sub_tree)

        for blob in self.blobs:
            yield GitFile(repo=self.repo, blob=blob)

    def get_file(self, path: pathlib.Path) -> GitFile:
        try:
            blob = self[path]
            return GitFile(repo=self.repo, blob=blob)
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

    @override
    def traverse(
        self, *args: Any, **kwargs: Any
    ) -> Iterator[IndexObjUnion] | Iterator[TraversedTreeTup]:
        yield from super().traverse(*args, **kwargs)

    def scandir(self) -> Generator[GitFile, GitTree]:
        yield from self


class GitCommit(Commit):
    """Represent A single Commit"""

    def __repr__(self) -> str:
        """:return: String with pythonic representation of our object"""
        return f"<{self.__class__.__name__}: {self.hexsha}>"

    @property
    def date(self) -> time.struct_time:
        return time.gmtime(self.committed_date)

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
            return pc.diff(other=self)

        for fl in self.tree.files:
            yield git.Diff(
                repo=self.repo,
                a_rawpath=None,
                b_rawpath=fl.blob.path,
                a_blob_id=None,
                b_blob_id=fl.blob.hexsha,
                a_mode=None,
                b_mode=str(fl.blob.mode),
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
            branch.name
            for branch in self.repo.branches
            if branch.commit.hexsha == self.hexsha
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


class GitHead(HEAD):
    @property
    def commit(self) -> GitCommit:
        return GitCommit(repo=self.repo, binsha=super().commit.binsha)


class GitRepo(Repo):
    def __repr__(self) -> str:
        """:return: String with pythonic representation of our object"""
        return f"<{self.__class__.__name__}: {pathlib.Path(self.git_dir).parent}>"

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
    def clone_from(cls, *args: list[Any], **kwargs: dict[str, Any]) -> Self:
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
    def __eq__(self, other: GitRepo | Repo) -> bool:
        if not isinstance(other, (GitRepo, Repo)):
            return False

        if isinstance(other, Repo):
            other = GitRepo.from_repo(other)

        return self.path == other.path

    @property
    def path(self) -> pathlib.Path:
        return pathlib.Path(self.working_dir)

    @override
    @property
    def branches(self) -> dict[str, str]:
        branches = {}
        for ref in self.branches:
            branches[ref.name] = ref.commit.hexsha
        return branches

    @override
    @property
    def description(self) -> str:
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
        self, num: int | None = None, since=None, until=None, branch=None, path=None
    ) -> Generator[GitCommit]:
        """Retrieve the commits of repository
        Args:
            num: Number of commits to retrieve
            since: timestamp since retrieve commits
            until: timestamp until to retrieve commits
        Returns:
            A list of Commit object
        """
        params = {}
        if since:
            params["since"] = since

        if until:
            params["until"] = until

        if num:
            params["max_count"] = num

        yield from self.iter_commits(rev=branch, paths=path, **params)

    def iter_commits(self, *args, **kwargs) -> Generator[GitCommit]:
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
    def tree(self) -> GitTree:
        return GitTree.from_tree(tree=super().tree())

    @property
    def head(self) -> GitHead:
        """
        :return:
            :class:`~git.refs.head.HEAD` object pointing to the current head reference
        """
        return GitHead(self, "HEAD")

    @classmethod
    def init(cls, path: pathlib.Path) -> Self:
        if path.exists():
            raise FileExistsError
        return super().init(path=path)

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

    def _checkout_branch_or_commit(
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

        try:
            self.pull()
            self.git.checkout(branch_name or hexsha)
        except GitCommandError:
            if branch_name:  # Create the branch if it doesn't exist yet
                self.git.checkout("-b", branch_name)
            else:
                raise

    def checkout_default_branch(self) -> None:
        self._checkout_branch_or_commit(branch_name=settings.DJANGO_GIT_BRANCH_NAME)

    def checkout_commit(self, hexsha) -> None:
        self._checkout_branch_or_commit(hexsha=hexsha)

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
        self.commit_and_push_project(
            settings.DJANGO_GIT_FIRST_COMMIT_MESSAGE,
            author_name=GIT_COMMITTER.name,
            author_email=GIT_COMMITTER.email,
            force_empty_commit=True,
        )
