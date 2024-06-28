class GitBaseError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class GitPathNotFoundError(GitBaseError):
    pass


class GitCommitNotFoundError(GitBaseError):
    pass


class GitBlobNotFoundError(GitBaseError):
    pass
