"""
config.py — Central Configuration Module
=========================================
All tunable settings for the PLC AI Automation System live here.
Override any setting by creating a .env file (copy .env.example).

Architecture note:
    This file is the single source of truth for paths, timing values,
    AI provider selection, and feature flags.  No magic numbers elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project root
load_dotenv(Path(__file__).parent / ".env")

# ──────────────────────────────────────────────────────────────
# BASE PATHS
# ──────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
ASSETS_DIR  = BASE_DIR / "assets"      # Reference screenshots for image matching
LOGS_DIR    = BASE_DIR / "logs"        # Log files
PROJECTS_DIR = BASE_DIR / "projects"  # Saved PLC projects

for _dir in (ASSETS_DIR, LOGS_DIR, PROJECTS_DIR):
    _dir.mkdir(exist_ok=True)

# ──────────────────────────────────────────────────────────────
# GX WORKS3 SETTINGS
# ──────────────────────────────────────────────────────────────
# Search order for the GX Works3 executable
GXW3_POSSIBLE_PATHS: list[str] = [
    os.getenv("GXW3_EXE_PATH", ""),
    r"C:\Program Files (x86)\MELSOFT\GXW3\GXW3.exe",
    r"C:\Program Files\MELSOFT\GXW3\GXW3.exe",
    r"C:\MELSOFT\GXW3\GXW3.exe",
]

GXW3_WINDOW_TITLE   = "GX Works3"   # Partial window-title match

# Default values used when creating a new project
DEFAULT_PROJECT_PATH   = os.getenv("DEFAULT_PROJECT_PATH", str(PROJECTS_DIR))
DEFAULT_PLC_SERIES     = "MELSEC iQ-R"
DEFAULT_PLC_TYPE       = "R04CPU"
DEFAULT_PROGRAM_LANG   = "Ladder"

# ──────────────────────────────────────────────────────────────
# TIMING SETTINGS  (seconds)
# ──────────────────────────────────────────────────────────────
# Increase these values on slower machines for more reliability.
LAUNCH_WAIT_TIME   = 6.0   # Wait after launching GX Works3 before interacting
DIALOG_WAIT_TIME   = 2.0   # Wait for a dialog to appear
CLICK_DELAY        = 0.4   # Pause after every simulated click
TYPE_DELAY         = 0.05  # Delay between individual keystrokes
SCREENSHOT_DELAY   = 0.3   # Settle time before capturing a screenshot
MAX_WAIT_TIME      = 30.0  # Hard timeout for any single wait loop
RETRY_DELAY        = 1.0   # Gap between retry attempts
MAX_RETRIES        = 3     # Number of retries for flaky operations

# ──────────────────────────────────────────────────────────────
# IMAGE MATCHING (OpenCV)
# ──────────────────────────────────────────────────────────────
IMAGE_MATCH_CONFIDENCE = 0.80   # 0.0 – 1.0; raise for stricter matching
IMAGE_MATCH_GRAYSCALE  = True   # Grayscale matching is faster

# ──────────────────────────────────────────────────────────────
# OCR (Tesseract)
# ──────────────────────────────────────────────────────────────
TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

# ──────────────────────────────────────────────────────────────
# AI / LLM  —  Anthropic Claude (primary)
# ──────────────────────────────────────────────────────────────
# Set ANTHROPIC_API_KEY in your .env file.
# Use "mock" for offline development/testing without an API key.
LLM_PROVIDER      = os.getenv("LLM_PROVIDER", "anthropic")   # "anthropic" | "mock"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")

# ──────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────
LOG_LEVEL     = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE      = LOGS_DIR / "automation.log"
LOG_ROTATION  = "10 MB"
LOG_RETENTION = "7 days"

# ──────────────────────────────────────────────────────────────
# AUTOMATION BEHAVIOR
# ──────────────────────────────────────────────────────────────
DEBUG_AUTOMATION    = os.getenv("DEBUG_AUTOMATION", "false").lower() == "true"
PYAUTOGUI_PAUSE     = 0.3   # Global pause injected between every pyautogui call
PYAUTOGUI_FAILSAFE  = True  # Move mouse to top-left corner to abort run
