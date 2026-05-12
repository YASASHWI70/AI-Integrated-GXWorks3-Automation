"""
models/ladder_logic.py — Intermediate Representation (IR) for Ladder Logic
===========================================================================

This module defines the canonical data format used throughout the system.
Every input source (natural language, JSON, PDF) is converted to these
Pydantic models before any automation step runs.

WHY AN INTERMEDIATE REPRESENTATION?
    - Decouples the AI parsing layer from the UI automation layer.
    - Makes the ladder logic serialisable to/from JSON for logging, replay,
      and future REST API support.
    - Enables validation before expensive UI actions are attempted.

LADDER LOGIC PRIMER (for beginners):
    A ladder diagram looks like electrical relay wiring drawn horizontally.
    Each horizontal line is called a "rung".  Left rail = power, right rail = neutral.

    Contacts  → [ X0 ]  input conditions (switch open/closed)
    Coils     → ( Y0 )  outputs that turn ON when the rung is TRUE
    Normally Open  (NO / a-contact): closed (passes) when address is ON
    Normally Closed (NC / b-contact): closed (passes) when address is OFF

    Start-Stop circuit (classic):
        |--[X0 START]--+--[/X1 STOP]--(Y0 MOTOR)--|
                       |                           |
                       +--[Y0 MOTOR]---------------+
        X0 ON  → latches Y0 ON.
        X1 ON  → opens NC contact → drops Y0 OFF.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────
# ENUMERATIONS
# ──────────────────────────────────────────────────────────────

class ElementType(str, Enum):
    """Every supported ladder element type in the MVP (and beyond)."""
    # Contacts
    CONTACT_NO    = "contact_no"      # Normally-Open  (a-contact)  [  ]
    CONTACT_NC    = "contact_nc"      # Normally-Closed (b-contact)  [/]
    CONTACT_RISE  = "contact_rise"    # Rising-edge detector
    CONTACT_FALL  = "contact_fall"    # Falling-edge detector

    # Coils
    COIL          = "coil"            # Standard output coil  ( )
    COIL_SET      = "coil_set"        # Set / latch coil      (S)
    COIL_RESET    = "coil_reset"      # Reset / unlatch coil  (R)

    # Timers
    TIMER_ON      = "timer_on"        # On-delay timer  TON
    TIMER_OFF     = "timer_off"       # Off-delay timer TOF

    # Counters
    COUNTER_UP    = "counter_up"      # Up-counter
    COUNTER_DOWN  = "counter_down"    # Down-counter

    # Branch markers (for parallel circuits)
    BRANCH_OPEN   = "branch_open"     # ORB / parallel branch start
    BRANCH_CLOSE  = "branch_close"    # ORB / parallel branch end


# ──────────────────────────────────────────────────────────────
# POSITION
# ──────────────────────────────────────────────────────────────

class Position(BaseModel):
    """
    Grid position of a ladder element.

    GX Works3 ladder editor uses a grid where:
        col → horizontal position (0 = leftmost, increases right)
        row → vertical position within a rung (0 = main rung,
               1+ = parallel branches below the main rung)
    """
    row: int = Field(0, ge=0, description="Vertical row (0 = main rung)")
    col: int = Field(0, ge=0, description="Horizontal column (0 = leftmost)")


# ──────────────────────────────────────────────────────────────
# LADDER ELEMENT
# ──────────────────────────────────────────────────────────────

class LadderElement(BaseModel):
    """
    A single element placed on the ladder grid.

    Examples
    --------
    NO contact at X0:
        LadderElement(type=ElementType.CONTACT_NO, address="X0",
                      label="START_BUTTON", position=Position(row=0, col=0))

    NC contact at X1 (stop button):
        LadderElement(type=ElementType.CONTACT_NC, address="X1",
                      label="STOP_BUTTON", position=Position(row=0, col=1))

    Output coil Y0:
        LadderElement(type=ElementType.COIL, address="Y0",
                      label="MOTOR", position=Position(row=0, col=2))

    Timer T0 with 5-second delay (preset=50 in 100 ms units):
        LadderElement(type=ElementType.TIMER_ON, address="T0",
                      preset=50, position=Position(row=0, col=2))
    """
    type:     ElementType
    address:  str            = Field(..., description="PLC address e.g. X0, Y0, M100, T0")
    label:    Optional[str]  = Field(None, description="Human-readable comment label")
    position: Position       = Field(default_factory=Position)
    preset:   Optional[int]  = Field(None, description="Timer/counter preset value")

    class Config:
        use_enum_values = True


# ──────────────────────────────────────────────────────────────
# LADDER RUNG
# ──────────────────────────────────────────────────────────────

class LadderRung(BaseModel):
    """
    One horizontal rung in the ladder diagram.

    A rung is a list of LadderElement objects.  Parallel branches are
    represented by elements sharing the same column but different rows.

    Rung IDs are 1-based (rung 1 is the first rung in the program).
    """
    id:       int                  = Field(..., ge=1, description="Rung number (1-based)")
    comment:  Optional[str]        = Field(None, description="Rung description / comment")
    elements: List[LadderElement]  = Field(default_factory=list)
    enabled:  bool                 = Field(True, description="False = rung is commented-out")

    def add_element(self, element: LadderElement) -> "LadderRung":
        """Fluent helper to append an element and return self."""
        self.elements.append(element)
        return self


# ──────────────────────────────────────────────────────────────
# LADDER PROGRAM
# ──────────────────────────────────────────────────────────────

class LadderProgram(BaseModel):
    """
    The complete ladder program that will be written into GX Works3.

    A program contains one or more rungs.
    In GX Works3 this maps to a single POU (Program Organisational Unit),
    usually named MAIN.
    """
    name:        str                = Field("MAIN", description="POU / program name")
    description: Optional[str]     = Field(None)
    rungs:       List[LadderRung]   = Field(default_factory=list)
    metadata:    Dict[str, Any]     = Field(default_factory=dict)

    def add_rung(self, rung: LadderRung) -> "LadderProgram":
        """Fluent helper to append a rung."""
        self.rungs.append(rung)
        return self

    def to_json(self) -> str:
        """Serialize to a pretty-printed JSON string for logging / storage."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "LadderProgram":
        """Deserialize from a JSON string."""
        return cls.model_validate_json(json_str)


# ──────────────────────────────────────────────────────────────
# PLC ADDRESS SPACE
# ──────────────────────────────────────────────────────────────

class PLCAddressSpace(BaseModel):
    """
    Describes the address prefix conventions for a specific PLC.
    Used by the validator to verify that addresses are in-range.

    Defaults match Mitsubishi MELSEC iQ-R / Q-series conventions.
    """
    input_prefix:    str = "X"    # Physical digital inputs
    output_prefix:   str = "Y"    # Physical digital outputs
    internal_prefix: str = "M"    # Internal relays
    timer_prefix:    str = "T"    # Timers
    counter_prefix:  str = "C"    # Counters
    data_prefix:     str = "D"    # Data registers

    input_max:    int = 0x1FFF   # Hex address max for inputs
    output_max:   int = 0x1FFF
    internal_max: int = 7999
    timer_max:    int = 511
    counter_max:  int = 255


# ──────────────────────────────────────────────────────────────
# FACTORY HELPERS  (common circuit patterns)
# ──────────────────────────────────────────────────────────────

def create_start_stop_circuit(
    start_contact: str = "X0",
    stop_contact:  str = "X1",
    output_coil:   str = "Y0",
    rung_id:       int = 1,
    comment:       str = "Start-Stop Motor Control Circuit",
) -> LadderRung:
    """
    Build a self-latching start-stop rung.

    Topology
    --------
        |--[ START ]--+--[/ STOP ]--(MOTOR)--|
                      |                      |
                      +--[ MOTOR ]-----------+

    How it works:
        1. Press START  → rung becomes TRUE  → MOTOR coil energises.
        2. MOTOR coil closes its own feedback contact (self-latch).
        3. Release START → rung stays TRUE via latch contact.
        4. Press STOP   → NC contact opens   → rung goes FALSE → MOTOR de-energises.
        5. Latch drops out; circuit is back to initial state.

    Args:
        start_contact: NO pushbutton address (e.g. "X0")
        stop_contact:  NC pushbutton address (e.g. "X1")
        output_coil:   Output coil address   (e.g. "Y0")
        rung_id:       1-based rung number
        comment:       Human-readable rung annotation

    Returns:
        A fully configured LadderRung ready to be passed to the automation layer.
    """
    return LadderRung(
        id=rung_id,
        comment=comment,
        elements=[
            # Column 0, Row 0: START pushbutton (NO contact)
            LadderElement(
                type=ElementType.CONTACT_NO,
                address=start_contact,
                label="START",
                position=Position(row=0, col=0),
            ),
            # Column 0, Row 1: MOTOR self-latch contact (parallel with START)
            LadderElement(
                type=ElementType.CONTACT_NO,
                address=output_coil,
                label="MOTOR_LATCH",
                position=Position(row=1, col=0),
            ),
            # Column 1, Row 0: STOP pushbutton (NC contact)
            LadderElement(
                type=ElementType.CONTACT_NC,
                address=stop_contact,
                label="STOP",
                position=Position(row=0, col=1),
            ),
            # Column 2, Row 0: MOTOR output coil
            LadderElement(
                type=ElementType.COIL,
                address=output_coil,
                label="MOTOR",
                position=Position(row=0, col=2),
            ),
        ],
    )


def create_simple_contact_coil(
    contact:  str = "X0",
    coil:     str = "Y0",
    rung_id:  int = 1,
    comment:  str = "Simple contact → coil",
) -> LadderRung:
    """
    The simplest possible rung: one NO contact drives one coil.

    Topology:  |--[ X0 ]--( Y0 )--|

    Useful as a sanity-check rung or as a building block.
    """
    return LadderRung(
        id=rung_id,
        comment=comment,
        elements=[
            LadderElement(
                type=ElementType.CONTACT_NO,
                address=contact,
                label="INPUT",
                position=Position(row=0, col=0),
            ),
            LadderElement(
                type=ElementType.COIL,
                address=coil,
                label="OUTPUT",
                position=Position(row=0, col=1),
            ),
        ],
    )
