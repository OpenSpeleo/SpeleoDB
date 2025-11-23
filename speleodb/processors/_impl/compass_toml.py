from __future__ import annotations

from functools import cached_property
from io import BytesIO
from pathlib import Path
from typing import Annotated

from packaging.version import Version
from pydantic import UUID4
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from tomlkit import dumps as toml_dumps
from tomlkit import parse as toml_parse

KNOWN_VERSIONS = [Version("0.0.1")]


class SpeleoDB(BaseModel):
    id: UUID4
    version: str

    # ------------------------------------------------------------
    # Validation: version must be known
    # ------------------------------------------------------------
    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        parsed_version = Version(v)
        if parsed_version not in KNOWN_VERSIONS:
            raise ValueError(f"Unknown version '{v}'")
        return v


class Project(BaseModel):
    name: str
    description: str | None = None
    mak_file: Annotated[str, Field()]
    dat_files: Annotated[list[str], Field(min_length=1)]
    plt_files: list[str] | None = None

    # ------------------------------------------------------------
    # Validation: mak_file must end with ".mak"
    # ------------------------------------------------------------
    @field_validator("mak_file")
    @classmethod
    def validate_mak_file(cls, v: str) -> str:
        if not v.lower().endswith(".mak"):
            raise ValueError("mak_file must end with .mak")
        return v

    # ------------------------------------------------------------
    # Validation: each dat file must end with ".dat"
    # ------------------------------------------------------------
    @field_validator("dat_files")
    @classmethod
    def validate_dat_files(cls, v: list[str]) -> list[str]:
        for item in v:
            if not item.lower().endswith(".dat"):
                raise ValueError(f"Invalid dat file '{item}', must end with .dat")
        return v

    # ------------------------------------------------------------
    # Validation: each plt file must end with ".plt"
    # (if provided)
    # ------------------------------------------------------------
    @field_validator("plt_files")
    @classmethod
    def validate_plt_files(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v

        for item in v:
            if not item.lower().endswith(".plt"):
                raise ValueError(f"Invalid plt file '{item}', must end with .plt")
        return v


class CompassConfig(BaseModel):
    __FILENAME__ = "compass.toml"

    speleodb: SpeleoDB
    project: Project

    @classmethod
    def from_toml(cls, source: str | Path | BytesIO) -> CompassConfig:
        """
        Load & validate a TOML file using tomlkit.
        Keeps comments and formatting structure.
        """
        match source:
            case str() | Path():
                path = source
                with Path(path).open("r", encoding="utf-8") as f:
                    toml_data = toml_parse(f.read())

            case BytesIO():
                toml_data = toml_parse(source.read().decode("utf-8"))

            case _:
                raise TypeError("source must be str, Path, or BytesIO")

        return cls.model_validate(toml_data)

    def to_toml(self, target: str | Path | BytesIO) -> None:
        """
        Serialize this model to TOML using tomlkit, preserving structure.
        """
        """
        Load & validate a TOML file using tomlkit.
        Keeps comments and formatting structure.
        """
        toml_str = toml_dumps(self.model_dump(mode="json"))

        match target:
            case str() | Path():
                Path(target).write_text(toml_str, encoding="utf-8")

            case BytesIO():
                target.write(toml_str.encode("utf-8"))

            case _:
                raise TypeError("target must be str, Path, or BytesIO")

    @cached_property
    def files(self) -> set[str]:
        return {
            CompassConfig.__FILENAME__,
            self.project.mak_file,
            *self.project.dat_files,
            *(plt_files if (plt_files := self.project.plt_files) else []),
        }
