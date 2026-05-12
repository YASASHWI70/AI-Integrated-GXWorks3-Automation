"""
models/plc_project.py — PLC Project Metadata Model
===================================================

Describes the project-level settings used when creating a new
GX Works3 project.  All automation tools that need project info
receive a PLCProject instance.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import config


class PLCSeries(str, Enum):
    """Supported Mitsubishi PLC series (expand as needed)."""
    IQ_R  = "MELSEC iQ-R"
    IQ_F  = "MELSEC iQ-F"
    Q     = "MELSEC-Q"
    L     = "MELSEC-L"
    FX5U  = "MELSEC iQ-F FX5U"


class PLCProject(BaseModel):
    """
    All information needed to create (or open) a GX Works3 project.

    Attributes
    ----------
    name:
        Project folder name.  Will be created under save_path.
    save_path:
        Directory where the project folder is written.
    plc_series:
        Hardware series selected in the New Project dialog.
    plc_type:
        Specific CPU model (e.g. "R04CPU", "FX5U").
    program_language:
        Initial programming language ("Ladder", "ST", "FBD", etc.).
    description:
        Optional project description stored in metadata.
    """
    name:             str         = Field("MyProject",  description="GX Works3 project name")
    save_path:        str         = Field(
        default_factory=lambda: config.DEFAULT_PROJECT_PATH,
        description="Folder where the project is saved",
    )
    plc_series:       PLCSeries   = Field(PLCSeries.IQ_R)
    plc_type:         str         = Field("R04CPU")
    program_language: str         = Field("Ladder")
    description:      Optional[str] = Field(None)

    @property
    def full_path(self) -> str:
        """Convenience: join save_path and project name."""
        from pathlib import Path
        return str(Path(self.save_path) / self.name)
