import contextlib
import re
import shutil
import time
from datetime import UTC
from datetime import datetime
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.utils.text import slugify
from django.utils.timezone import get_default_timezone
from git.exc import GitCommandError

from speleodb.git_engine.core import GitCommit
from speleodb.git_engine.exceptions import GitBaseError
from speleodb.processors.artifact import Artifact
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.utils.timing_ctx import timed_section

# ruff: noqa: E501


class BaseFileProcessor:
    ALLOWED_EXTENSIONS = ["*"]
    ALLOWED_MIMETYPES = ["*"]

    REJECTED_EXTENSIONS = [
        # Executable files
        ".exe",  # Windows Executable File. Can execute programs and potentially harmful code.
        ".bat",  # Batch File. Used to execute commands in Windows; can automate harmful scripts.
        ".cmd",  # Command Script. Similar to .bat but with enhanced scripting features.
        ".com",  # Command File. Old-style executable in DOS/Windows.
        ".msi",  # Microsoft Installer Package. Can install or execute programs.
        ".msp",  # Microsoft Installer Patch. Can be used to deliver harmful updates.
        ".scr",  # Windows Screensaver File. Often executable and a common malware disguise.
        # Script files
        ".vbs",  # VBScript File. Used in Windows scripting; can automate malicious actions.
        ".js",  # JavaScript File. Can execute scripts on local machines or browsers.
        ".jse",  # Encoded JavaScript File. Often used to obfuscate malicious scripts.
        ".wsf",  # Windows Script File. Can execute VBScript or JScript on a Windows system.
        ".ps1",  # PowerShell Script. Can execute commands on Windows with administrative privileges.
        ".sh",  # Shell Script. Used on Unix/Linux for executing commands, potentially harmful.
        ".php",  # PHP Script. Can execute on servers or, if misconfigured, on a local machine.
        ".pl",  # Perl Script. Can automate tasks, including malicious actions.
        ".py",  # Python Script. Can execute harmful scripts on systems with Python installed.
        ".rb",  # Ruby Script. Can execute harmful actions on systems with Ruby installed.
        ".lua",  # Lua Script. Can execute harmful actions on systems with Lua installed.
        ".go",  # GO Script. Can execute harmful actions on systems with GO installed.
        # Macro and document files with potential for embedded malware
        ".docm",  # Word Document with Macros. Macros can run malicious code.
        ".xlsm",  # Excel Workbook with Macros. Macros can run harmful scripts.
        ".pptm",  # PowerPoint Presentation with Macros. Similar risk as .docm and .xlsm.
        ".dotm",  # Word Macro-Enabled Template. Macros can execute malicious scripts.
        # Web and ActiveX-related files
        ".html",  # HTML File. Can include malicious scripts if opened locally.
        ".htm",  # HTML File. Same risk as .html.
        ".mht",  # MHTML File. May contain embedded scripts or links to harmful code.
        ".hta",  # HTML Application. Executable format for web-based apps, often abused by malware.
        # Archive files (can contain harmful executables)
        ".zip",  # ZIP Archive. Can conceal malicious files.
        ".rar",  # RAR Archive. Similar risk as .zip.
        ".7z",  # 7-Zip Archive. Similar risk as .zip.
        ".iso",  # Disk Image File. Can contain harmful executables.
        ".gz",  # Gzip Archive. Can contain malicious scripts or binaries.
        # System and configuration files
        ".sys",  # Windows System File. Can be exploited to modify or harm the system.
        ".dll",  # Dynamic Link Library. Can be injected into processes to execute malicious code.
        ".drv",  # Driver File. Can be used to exploit hardware or system vulnerabilities.
        ".inf",  # Setup Information File. Can automate installation of malicious software.
        ".plist",  # macOS/iOS Property List File. Can contain malicious configurations.
        # Mobile-related files
        ".apk",  # Android Package File. Can install malicious applications on Android devices.
        ".dex",  # Dalvik Executable File. Used in Android; can execute malicious code.
        ".ipa",  # iOS App Package. Can install harmful applications on iOS devices.
        # macOS-related files
        ".app",  # macOS Application Bundle. Can execute programs and potentially harmful code.
        ".dmg",  # macOS Disk Image. Can contain harmful applications.
        ".pkg",  # macOS Installer Package. Can install malicious software.
        ".command",  # macOS Executable Script. Can run harmful shell scripts.
        # Linux-related files
        ".bin",  # Binary Executable File. Commonly used on Linux, can execute harmful programs.
        ".run",  # Linux Executable File. Often used for installers or scripts.
        ".deb",  # Debian Package. Can install software, including malicious programs.
        ".rpm",  # Red Hat Package Manager File. Similar risk as .deb.
        ".so",  # Shared Object File. Can be used to inject malicious code into applications.
        # Other potentially harmful files
        ".reg",  # Windows Registry File. Can modify or harm the Windows registry.
        ".lnk",  # Windows Shortcut File. Can link to and execute malicious programs.
        ".jar",  # Java Archive File. Can execute harmful Java programs.
        ".class",  # Java Class File. Compiled Java bytecode, potentially harmful.
        ".psd1",  # PowerShell Data File. Can accompany malicious PowerShell scripts.
        ".psm1",  # PowerShell Module File. Similar risk as PowerShell scripts.
    ]

    ASSOC_FILEFORMAT = Format.FileFormat.OTHER

    TARGET_FOLDER = "misc"
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None

    DATETIME_FORMAT = "%Y-%m-%d_%Hh%M"

    def __init__(self, project: Project, hexsha: str | None = None) -> None:
        self.project = project
        self.hexsha = hexsha

    # -------------------------- Getters & Setters -------------------------- #

    @property
    def project(self) -> Project:
        return self._project

    @project.setter
    def project(self, value: Project) -> None:
        if not isinstance(value, Project):
            raise TypeError(f"Invalid Project type: `{type(value)}`.")

        self._project = value

    @property
    def hexsha(self) -> str | None:
        return self._hexsha

    @hexsha.setter
    def hexsha(self, value: str) -> None:
        if value is not None and not self.validate_hexsha(value):
            raise ValueError(f"Invalid Git SHA value: `{value}`.")

        self._hexsha = value

    @property
    def source_f(self) -> Path:
        source_f = self.project.git_repo.path / self.TARGET_SAVE_FILENAME
        if not source_f.is_file():
            raise ValidationError(f"Impossible to find the file: `{source_f}` ...")
        return source_f

    # ------------------------------ Validators ----------------------------- #

    def validate_hexsha(self, hexsha: str) -> bool:
        """
        Verify if the provided hexsha is a valid Git SHA (could be a full or partial).
        A valid partial SHA-1 can be between 4 and 40 hexadecimal characters long.
        """
        # Regular expression for a valid partial or full Git SHA-1 hash
        git_sha_pattern = r"^[a-fA-F0-9]{4,40}$"

        # Return True if the hexsha matches the pattern, else False
        return bool(re.match(git_sha_pattern, hexsha))

    # ----------------------------- Public APIs ----------------------------- #

    def add_file_to_project(
        self, file: InMemoryUploadedFile | TemporaryUploadedFile
    ) -> Artifact:
        artifact = Artifact(file)
        artifact.assert_valid(
            allowed_extensions=self.ALLOWED_EXTENSIONS,
            allowed_mimetypes=self.ALLOWED_MIMETYPES,
            rejected_extensions=self.REJECTED_EXTENSIONS,
        )

        target_path = self._get_storage_path(artifact=artifact)

        with timed_section("File copy to project dir"):
            artifact.write(path=target_path)

        return artifact

    def get_file_for_download(self, target_f: Path) -> Path:
        if not isinstance(target_f, Path):
            target_f = Path(target_f)

        # 1. Fetch the commit requested by the user - pull repository if needed.
        try:
            if self.hexsha is not None:
                try:
                    commit = self.project.git_repo.commit(self.hexsha)
                except ValueError:
                    # In case the commit doesn't exist - pull and retry
                    self.project.git_repo.pull()
                    commit = self.project.git_repo.commit(self.hexsha)
            else:
                # If we select the HEAD commit - no other choice than pull first
                self.project.git_repo.pull()
                commit = self.project.git_repo.head.commit

            if commit is None:
                raise ValueError  # noqa: TRY301

        except (ValueError, GitBaseError, GitCommandError) as e:
            raise RuntimeError(f"Impossible to find commit: `{self.hexsha}`") from e

        # 2. Generate or copy the file to be downloaded to path `target_f`:
        # What file(s) to download is determined by the `Processor` class.
        try:
            self._generate_or_copy_file_for_download(commit=commit, target_f=target_f)

            if not target_f.is_file():
                raise RuntimeError(f"The file `{target_f}` does not exist.")

        except PermissionError as e:
            raise RuntimeError from e

        # 3. Fetch the date at which the commit was submitted.
        commit_date = time.gmtime(commit.committed_date)

        # 4. Convert `time.struct_time` to datetime to be "timezone-aware"
        naive_datetime = datetime(*commit_date[:6], tzinfo=UTC)
        tz_aware_datetime = naive_datetime.astimezone(tz=get_default_timezone())

        # 5. Generate the filename that will be seen in the browser
        return (
            self.TARGET_DOWNLOAD_FILENAME.format(
                project_name=slugify(self.project.name, allow_unicode=False).lower(),
                timestamp=tz_aware_datetime.strftime(self.DATETIME_FORMAT),
            )
            if self.TARGET_DOWNLOAD_FILENAME is not None
            else target_f.name
        )

    # ----------------------------- Private APIs ----------------------------- #

    # ~~~~~~~~~~~~~ Download API ~~~~~~~~~~~~~ #

    def _generate_or_copy_file_for_download(
        self, commit: GitCommit, target_f: Path
    ) -> None:
        with contextlib.suppress(shutil.SameFileError):
            shutil.copy(src=self.source_f, dst=target_f)

    # ~~~~~~~~~~~~~ Upload APIs ~~~~~~~~~~~~~ #

    def _get_storage_path(self, artifact: Artifact) -> Path:
        """This returns the full file path where the file will be stored.
        If needed, the corresponding folder will be created."""

        folder = self.project.git_repo.path
        if self.TARGET_FOLDER is not None:
            folder: Path = folder / self.TARGET_FOLDER
            folder.mkdir(parents=True, exist_ok=True)

        filename = self._validate_and_get_storage_name(folder=folder, artifact=artifact)

        return folder / filename

    def _validate_and_get_storage_name(self, folder: Path, artifact: Artifact) -> str:
        """This generates the filename to be used while stored in git.
        This function may implement some collision avoidance logic.

        This function is not designed to be subclassed - use `_get_storage_name` instead

        If collision is detected - raises `FileExistsError`.
        """

        if not isinstance(folder, Path):
            folder = Path(folder)

        if not folder.exists():
            raise FileNotFoundError(f"The folder: `{folder}` does not exists.")

        if not folder.is_dir():
            raise TypeError(f"The folder: `{folder}` is not a folder.")

        if not isinstance(artifact, Artifact):
            raise TypeError(
                f"The artifact `{artifact}` is of unknown type: `{type(artifact)}`."
            )

        return self._get_storage_name(folder=folder, artifact=artifact)

    def _get_storage_name(self, folder: Path, artifact: Artifact) -> str:
        return (
            self.TARGET_SAVE_FILENAME
            if self.TARGET_SAVE_FILENAME is not None
            else artifact.name
        )
