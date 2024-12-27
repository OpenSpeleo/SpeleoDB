import contextlib
import logging
import pathlib
import time
from io import BytesIO
from typing import Self

import git
from django.conf import settings
from git import HEAD
from git import Commit
from git import Repo
from git import Tree
from git.exc import GitCommandError
from git.exc import InvalidGitRepositoryError

from speleodb.git_engine.exceptions import GitBaseError
from speleodb.git_engine.exceptions import GitBlobNotFoundError
from speleodb.git_engine.exceptions import GitPathNotFoundError

GIT_COMMITTER = git.Actor("SpeleoDB", "contact@speleodb.com")

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


class GitFile:
    def __init__(self, repo, blob):
        self._blob = blob
        self.repo = repo

    @classmethod
    def from_hexsha(cls, repo, hexsha):
        blob = repo.blob(hexsha)
        return cls(repo=repo, blob=blob)

    @property
    def repo(self):
        if not isinstance(self._repo, GitRepo):
            return GitRepo.from_repo(self._repo)
        return self._repo

    @repo.setter
    def repo(self, value):
        if not isinstance(value, GitRepo):
            value = GitRepo.from_repo(value)
        self._repo = value

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.abspath}>"

    @property
    def commit(self):
        for commit in self.repo.iter_commits(all=True, paths=self.path):
            if self.binsha in commit.tree.blob_binshas:
                return commit
        raise FileNotFoundError

    @property
    def blob(self):
        return self._blob

    @property
    def content(self):
        data = BytesIO(self._blob.data_stream.read())
        data.name = self.name
        return data

    @property
    def name(self):
        return self.blob.name

    @property
    def abspath(self):
        return pathlib.Path(self.blob.abspath)

    @property
    def path(self):
        return pathlib.Path(self.blob.path)

    @property
    def mode(self):
        return self.blob.mode

    @property
    def size(self):
        return self.blob.size

    @property
    def type(self):
        return self.blob.type

    @property
    def binsha(self) -> str:
        return self.blob.binsha

    @property
    def hexsha(self) -> str:
        return self.blob.hexsha


class GitDir:
    def __init__(self, tree, parent=None):
        self._tree = tree
        self._parent = parent

    @property
    def tree(self):
        return self._tree

    @property
    def parent(self):
        return self._parent

    @property
    def files(self):
        return [GitFile(repo=self.tree.repo, blob=blob) for blob in self.tree.blobs]

    @property
    def root_files(self):
        return [
            GitFile(repo=self.tree.repo, blob=blob)
            for blob in self.tree.blobs
            if blob.path.parent == "."
        ]

    @property
    def subdirs(self):
        return [GitDir(subTree) for subTree in self.tree.trees]


class GitTree(Tree):
    @classmethod
    def from_tree(cls, tree):
        if not isinstance(tree, Tree):
            return TypeError(f"Expected `git.Tree` type, received: {type(tree)}")

        return cls(repo=tree.repo, binsha=tree.binsha, mode=tree.mode, path=tree.path)

    @property
    def repo(self):
        if not isinstance(self._repo, GitRepo):
            return GitRepo.from_repo(self._repo)
        return self._repo

    @repo.setter
    def repo(self, value):
        if not isinstance(value, GitRepo):
            value = GitRepo.from_repo(value)
        self._repo = value

    @property
    def root(self):
        """Retreive the root tree"""
        root = [GitDir(subTree) for subTree in self.trees]
        root.extend([GitFile(repo=self.repo, blob=blob) for blob in self.blobs])

        return root

    def get_file(self, path: pathlib.Path):
        try:
            blob = self[path]
            return GitFile(repo=self.repo, blob=blob)
        except KeyError as e:
            raise GitPathNotFoundError("Path:" + path + " not found") from e

    def __get_tree_files__(self, tree, recursive=True):
        files = [GitFile(repo=self.repo, blob=blob) for blob in tree.blobs]

        if recursive:
            for subtree in tree.trees:
                files.extend(self.__get_tree_files__(subtree, recursive=True))

        return files

    @property
    def files(self):
        """Retrieve all files in the tree
        Return:
            return a GitFile list
        """
        return self.__get_tree_files__(self)

    @property
    def root_files(self):
        """Retrieve all files in the tree
        Return:
            return a GitFile list
        """
        return self.__get_tree_files__(self, recursive=False)

    @property
    def blob_binshas(self):
        return [blob.binsha for blob in self.blobs]

    def traverse(self, *args, **kwargs):
        for blob in super().traverse(*args, **kwargs):
            yield GitFile(repo=self.repo, blob=blob)


class GitCommit(Commit):
    """Represent A single Commit"""

    @property
    def date(self):
        return time.gmtime(self.committed_date)

    @property
    def hexsha_short(self) -> str:
        """
        Returns the short version of the commit hash (7 characters by GitHub standard).
        """
        return self.hexsha[:7]

    @property
    def repo(self):
        if not isinstance(self._repo, GitRepo):
            self._repo = GitRepo.from_repo(self._repo)
        return self._repo

    @repo.setter
    def repo(self, value):
        if not isinstance(value, GitRepo):
            value = GitRepo.from_repo(value)
        self._repo = value

    @property
    def changes(self):
        """Retrieve the tree changes from parents"""

        with contextlib.suppress(IndexError):
            pc = self.repo.commit(self.parents[0])
            return pc.diff(other=self)

        return [
            git.Diff(
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
            for fl in self.tree.files
        ]

    @property
    def tree(self):
        if isinstance(self._tree, GitTree):
            return self._tree
        return GitTree.from_tree(self._tree)

    @tree.setter
    def tree(self, value):
        if not isinstance(value, GitTree):
            value = GitTree.from_tree(value)
        self._tree = value

    @property
    def tags(self):
        return [tag.name for tag in self.repo.tags if tag.commit.hexsha == self.hexsha]

    @property
    def branches(self):
        return [
            branch.name
            for branch in self.repo.branches
            if branch.commit.hexsha == self.hexsha
        ]

    @property
    def files(self):
        return self.tree.files

    @property
    def root_files(self):
        """Retrieve all files in the root of the tree
        Return:
            return a GitFile list
        """
        return self.tree.root_files


class GitHead(HEAD):
    @property
    def commit(self) -> GitCommit:
        return GitCommit(repo=self.repo, binsha=super().commit.binsha)


class GitRepo(Repo):
    @classmethod
    def from_directory(cls, directory: pathlib.Path) -> Self:
        if not isinstance(directory, pathlib.Path):
            directory = pathlib.Path(directory)

        if not directory.is_dir():
            directory.unlink(missing_ok=True)
            raise RuntimeError(f"The folder `{directory}` is not a folder.")

        try:
            return cls(directory)
        except InvalidGitRepositoryError as e:
            directory.unlink(missing_ok=True)
            raise RuntimeError from e

    @classmethod
    def from_repo(cls, repo: Repo) -> Self:
        return cls(repo.working_dir)

    @classmethod
    def clone_from(cls, *args, **kwargs) -> Self:
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

    def __eq__(self, other) -> bool:
        if not isinstance(other, (GitRepo, Repo)):
            return False

        if isinstance(other, Repo):
            other = GitRepo.from_repo(other)

        return self.path == other.path

    @property
    def path(self) -> pathlib.Path:
        return pathlib.Path(self.working_dir)

    @property
    def branches(self) -> dict[str, str]:
        branches = {}
        for ref in self.branches:
            branches[ref.name] = ref.commit.hexsha
        return branches

    @property
    def description(self):
        try:
            return self.description
        except OSError:
            return None

    def commit(self, rev=None):
        if rev is None:
            return self.head.commit
        """Retrieve a GitCommit object represent single commit from reporistory"""
        return GitCommit(repo=self, binsha=super().commit(rev).binsha)

    @property
    def commits(self):
        from speleodb.utils.gitlab_manager import GitlabManager

        return [
            commit
            for commit in self.get_commits()
            if commit.message != GitlabManager.FIRST_COMMIT_NAME
        ]

    def get_commits(self, num=None, since=None, until=None, branch=None, path=None):
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

        return self.iter_commits(rev=branch, paths=path, **params)

    def iter_commits(self, *args, **kwargs):
        commits = super().iter_commits(*args, **kwargs)

        for commit in commits:
            yield GitCommit(repo=self, binsha=commit.binsha)

    @property
    def tree(self):
        return GitTree.from_tree(tree=super().tree())

    def get_tree_file(self, path: pathlib.Path):
        return self.tree.getFile(path)

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
        path.mkdir(parents=True)

        return super().init(path=path, bare=True)

    def pull(self):
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
    ):
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
        except git.exc.GitCommandError:
            if branch_name:  # Create the branch if it doesn't exist yet
                self.git.checkout("-b", branch_name)
            else:
                raise

    def checkout_default_branch(self):
        self._checkout_branch_or_commit(branch_name=settings.DJANGO_GIT_BRANCH_NAME)

    def checkout_commit(self, hexsha):
        self._checkout_branch_or_commit(hexsha=hexsha)

    def commit_and_push_project(
        self, message: str, author_name: str, author_email: str
    ) -> str | None:
        # Add every file pending
        self.index.add("*")

        # If there are modified files:
        if self.is_dirty():
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

    def find_blob(self, hexsha: str):
        for commit in self.iter_commits():
            for blob in commit.tree.traverse():
                if blob.hexsha == hexsha:
                    return blob

        raise GitBlobNotFoundError(f"Git Object with id `{hexsha}` not found.")
