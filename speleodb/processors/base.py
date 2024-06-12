import shutil
import time
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from speleodb.surveys.models import Project
from speleodb.users.models import User
from speleodb.utils.exceptions import ProjectNotFound


class BaseFileProcessor:
    ALLOWED_EXTENSIONS = None
    ALLOWED_MIMETYPE = None
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None

    def __init__(self, file):
        self._file = file
        self.assert_valid()

    @property
    def file(self):
        return self._file

    @property
    def file_ext(self):
        return Path(self._file.name).suffix.lower()

    @property
    def content_type(self):
        return self.file.content_type

    def assert_valid(self):
        if self.content_type not in self.ALLOWED_MIMETYPE:
            raise ValidationError(
                f"Invalid file type received: `{self.content_type}`, "
                f"expected one of: {self.ALLOWED_MIMETYPE}"
            )

        if self.file_ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Invalid file extension received: `{self.file_ext}`, "
                f"expected one of: {self.ALLOWED_EXTENSIONS}"
            )

        return True

    def preprocess_file_before_upload(self, user: User, project: Project):
        return self._file.read()

    def commit_uploaded_file(self, user: User, project: Project, commit_msg: str):
        # Make sure the project is update to ToT (Top of Tree)
        project.git_repo.checkout_and_pull()

        file = self.preprocess_file_before_upload(user=user, project=project)

        with (project.git_repo.path / self.TARGET_SAVE_FILENAME).open(mode="wb") as f:
            f.write(file)

        return project.git_repo.commit_and_push_project(message=commit_msg, user=user)

    @classmethod
    def checkout_commit_or_master(cls, project: Project, commit_sha1=None):
        if not project.git_repo:
            raise ProjectNotFound("This project does not exist on gitlab or on drive")

        if commit_sha1 is None:
            # Make sure the project is update to ToT (Top of Tree)
            project.git_repo.checkout_branch_or_commit(branch_name="master")
            project.git_repo.pull()

        else:
            project.git_repo.checkout_branch_or_commit(commit_sha1=commit_sha1)

    @classmethod
    def postprocess_file_before_download(cls, filepath: Path, project: Project):
        raise NotImplementedError

    @classmethod
    def prepare_file_for_download(cls, project: Project, commit_sha1=None):
        cls.checkout_commit_or_master(project=project, commit_sha1=commit_sha1)

        dest_dir = settings.DJANGO_TMP_DL_DIR / project.git_repo.commit_sha1

        # create an empty directory storing the artifact
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(exist_ok=True, parents=True)

        dl_filepath = dest_dir / cls.TARGET_DOWNLOAD_FILENAME.format(
            timestamp=time.strftime("%Y-%m-%d_%Hh%M", project.git_repo.commit_date)
        )

        return cls.postprocess_file_before_download(dl_filepath, project=project)
