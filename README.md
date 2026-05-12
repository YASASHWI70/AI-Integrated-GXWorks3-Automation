# PLC AI Automation System for GX Works3

An AI-powered system that converts natural language, JSON, or PDF
specifications into Mitsubishi PLC ladder logic — and then **automatically
writes that logic into GX Works3** using UI automation.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Folder Structure](#folder-structure)
3. [Layer Responsibilities](#layer-responsibilities)
4. [Quick Start](#quick-start)
5. [Installation](#installation)
6. [Usage Examples](#usage-examples)
7. [MCP Architecture Explained](#mcp-architecture-explained)
8. [Automation Stability Best Practices](#automation-stability-best-practices)
9. [Milestone 1 — What the MVP Achieves](#milestone-1)
10. [Scaling Roadmap](#scaling-roadmap)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     USER INPUT                          │
│     (text / JSON / PDF / structured LadderProgram)      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  AI REASONING LAYER                     │
│  InputParser → NLPParser → LadderGenerator (LLM/rules)  │
│  Converts any input into a LadderProgram JSON model.    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 VALIDATION LAYER                        │
│  LadderValidator — checks addresses, coil conflicts,   │
│  timer presets, rung structure BEFORE automation.       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              MCP TOOL EXECUTION LAYER                   │
│  ToolRegistry + ToolExecutor                            │
│  Translates LadderProgram into a sequence of tool calls:│
│  open_gxworks3 → create_project → open_ladder_editor   │
│  → insert_contact → insert_coil → save_project         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                UI AUTOMATION LAYER                      │
│  GXWorks3Interface                                      │
│  MouseController + KeyboardController                   │
│  ImageMatcher (OpenCV) + OCREngine (Tesseract)          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   GX Works3      │
              │ (Mitsubishi PLC  │
              │  IDE software)   │
              └──────────────────┘
```

---

## Folder Structure

```
plc_ai_automation/
│
├── main.py                    ← Entry point & orchestrator
├── config.py                  ← All settings in one place
├── requirements.txt
├── .env.example               ← Copy to .env and fill in your settings
│
├── models/                    ← Pydantic data models (Intermediate Representation)
│   ├── ladder_logic.py        ← LadderProgram, LadderRung, LadderElement
│   ├── tool_result.py         ← ToolResult (uniform return type for all tools)
│   └── plc_project.py         ← PLCProject (new project settings)
│
├── mcp_layer/                 ← MCP-style tool execution framework
│   ├── tool_registry.py       ← Register & look up tools by name
│   ├── tool_executor.py       ← Run tools with retry & logging
│   └── tools/
│       ├── base_tool.py       ← Abstract base class every tool inherits
│       ├── open_gxworks3.py   ← Tool: launch GX Works3
│       ├── create_project.py  ← Tool: File → New Project
│       ├── open_ladder_editor.py ← Tool: navigate to MAIN POU
│       ├── insert_contact.py  ← Tool: insert NO/NC contact (F5/F6)
│       ├── insert_coil.py     ← Tool: insert coil (F7)
│       └── save_project.py    ← Tool: Ctrl+S
│
├── automation_layer/          ← Low-level UI automation primitives
│   ├── screen_manager.py      ← Screenshots, window focus, window rect
│   ├── mouse_keyboard.py      ← Clicks, typing, hotkeys (pyautogui wrappers)
│   ├── image_matcher.py       ← OpenCV template matching
│   ├── ocr_engine.py          ← Tesseract OCR for reading screen text
│   └── gxworks3_interface.py  ← GX Works3 facade (cell navigation, etc.)
│
├── ai_layer/                  ← AI reasoning (LLM integration)
│   ├── input_parser.py        ← Detect format & normalise user input
│   ├── ladder_generator.py    ← LLM + rule-based ladder logic generation
│   └── llm_client.py          ← OpenAI / Anthropic / Mock provider
│
├── parsers/                   ← Format-specific parsers
│   ├── nlp_parser.py          ← Keyword NLP, address extraction
│   ├── json_parser.py         ← Full schema + shorthand JSON
│   └── pdf_parser.py          ← pdfplumber / PyPDF2 text extraction
│
├── validation_layer/          ← Pre-automation checks
│   ├── ladder_validator.py    ← Logic rules: addresses, coils, structure
│   └── screen_validator.py    ← Post-step UI state verification
│
├── assets/                    ← Reference screenshots for image matching
│   └── (place PNG templates here — see Automation Stability section)
│
├── examples/
│   ├── start_stop.json        ← Shorthand JSON example
│   └── motor_with_timer.json  ← Full schema JSON example
│
├── projects/                  ← GX Works3 projects saved here
└── logs/                      ← automation.log (auto-created)
```

---

## Layer Responsibilities

| Layer | What it knows | What it does NOT know |
|---|---|---|
| **AI Layer** | User intent, LLM APIs, ladder patterns | GX Works3 UI, screen coordinates |
| **MCP Layer** | Tool names, parameter schemas, retry logic | How tools are implemented internally |
| **Automation Layer** | Screen pixels, keyboard shortcuts, OpenCV | What ladder logic means, PLC semantics |
| **Validation Layer** | Mitsubishi address conventions, logic rules | How to open GX Works3 |

---

## Quick Start

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | [python.org](https://python.org) |
| GX Works3 | Installed in a default MELSOFT path |
| Tesseract OCR | [Download](https://github.com/UB-Mannheim/tesseract/wiki) — optional for MVP |
| OpenAI / Anthropic key | Optional — system works in mock mode without one |

### Installation

```bash
# 1. Clone / copy the project
cd C:\
# (project is already at C:\plc_ai_automation)

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your environment
copy .env.example .env
# Edit .env — set GXW3_EXE_PATH and optionally LLM_PROVIDER + API key
```

---

## Usage Examples

```bash
# Demo mode — parse & validate without touching GX Works3
python main.py --demo --input "Create a start-stop motor circuit"

# Natural language → full automation
python main.py --input "I need a start-stop circuit. X0=start, X1=stop, Y0=motor"

# JSON shorthand
python main.py --input '{"type":"start_stop","start":"X0","stop":"X1","output":"Y0"}'

# JSON file (full schema)
python main.py --file examples/motor_with_timer.json --project MyMotorProject

# PDF specification
python main.py --file "C:\specs\pump_control.pdf" --project PumpProject

# Interactive mode (no arguments)
python main.py
```

---

## MCP Architecture Explained

MCP (Model Context Protocol) is a pattern that separates
*what to do* (decided by the AI) from *how to do it* (implemented by tools).

### Why MCP?

Without MCP:
```
AI model → directly calls pyautogui.click(...)  ← tightly coupled, hard to test
```

With MCP:
```
AI model → "call insert_contact(address='X0')"
           ↓
     ToolExecutor → looks up InsertContactTool in registry
                  → validates parameters
                  → runs execute() with retry
                  → returns ToolResult
```

### Adding a New Tool

1. Create `mcp_layer/tools/my_new_tool.py`:
```python
from .base_tool import BaseTool
from models.tool_result import ToolResult

class MyNewTool(BaseTool):
    name        = "my_new_tool"
    description = "Does X in GX Works3."
    parameters  = {"type": "object", "properties": {"address": {"type": "string"}}}

    def execute(self, address: str = "X0", **kwargs) -> ToolResult:
        # ... automation code ...
        return ToolResult.success(self.name, message=f"Done: {address}")
```

2. Register it in `mcp_layer/tool_registry.py`:
```python
from .tools.my_new_tool import MyNewTool
registry.register(MyNewTool)
```

3. Call it:
```python
executor.execute("my_new_tool", {"address": "X5"})
```

---

## Automation Stability Best Practices

UI automation is inherently fragile.  Here are the practices built into this
system — and guidance for making it even more reliable:

### 1. Use keyboard shortcuts over mouse clicks
```
✓  gx.keyboard.press("f5")         # F5 always inserts a contact
✗  gx.mouse.click(toolbar_btn_x, y) # button may move with window resize
```

### 2. Add explicit delays between steps
```python
# config.py — tune these on your machine
CLICK_DELAY      = 0.4   # increase to 0.8 on slow machines
LAUNCH_WAIT_TIME = 6.0   # increase if GX Works3 takes longer to load
```

### 3. Build template images for critical UI states
Place PNG screenshots in `assets/`:
```
assets/
  ladder_editor_active.png   ← taken when ladder editor is open
  ok_button.png              ← OK button in common dialogs
  new_project_dialog.png     ← New Project dialog header
```
The `ImageMatcher` uses these to verify UI state before acting.

### 4. Verify after each step (ScreenValidator)
```python
screen_val = ScreenValidator()
result     = screen_val.check_no_error_dialog()
if not result.all_passed:
    raise RuntimeError("Unexpected dialog after insertion!")
```

### 5. Set GX Works3 to a known state at startup
- Maximise the window
- Use a consistent screen resolution (1920×1080 recommended)
- Disable any Windows display scaling other than 100%
- Close all other GX Works3 projects before running automation

### 6. Take debug screenshots on failure
```python
gx.take_debug_screenshot("before_insert_contact")
```
Screenshots are saved to `logs/` with timestamps.

---

## Milestone 1

The MVP achieves this exact sequence:

```
1. Open GX Works3          open_gxworks3()
2. Create a new project    create_project(name="PLCAIProject")
3. Open ladder editor      open_ladder_editor()
4. Insert X0 NO contact    insert_contact(address="X0", col=0)
5. Insert Y0 latch contact insert_contact(address="Y0", col=0, row=1)
6. Insert X1 NC contact    insert_contact(address="X1", col=1, normally_closed=True)
7. Insert Y0 coil          insert_coil(address="Y0", col=2)
8. Save project            save_project()
```

Run it:
```bash
python main.py --input "start stop motor X0 X1 Y0" --project Milestone1
```

---

## Scaling Roadmap

### Phase 2 — More Instructions
- [ ] Add `insert_timer.py` tool (TON, TOF)
- [ ] Add `insert_counter.py` tool (CTU, CTD)
- [ ] Add `insert_comparison.py` tool (CMP, >, <, =)
- [ ] Support SET/RESET coil variants

### Phase 3 — Better UI Recognition
- [ ] Build a library of asset templates at multiple DPI scales
- [ ] Add region-based OCR to verify inserted addresses
- [ ] Use YOLO or LayoutLM to understand GX Works3 UI structure
- [ ] Vision-language model for screenshot understanding

### Phase 4 — Multi-Vendor Support
- [ ] Adapter pattern: swap `GXWorks3Interface` for `TIAPortalInterface`
  or `RSLogix5000Interface` by implementing the same abstract API
- [ ] Normalise address schemes per vendor in `PLCAddressSpace`

### Phase 5 — Agentic Workflows
- [ ] Multi-step planning: break "design conveyor control system" into
  sub-tasks automatically
- [ ] Self-correction: detect insertion errors via OCR, auto-retry with
  different approach
- [ ] Human-in-the-loop: pause workflow for engineer review at checkpoints
- [ ] ReAct-style reasoning: AI observes screen state and decides next action

### Phase 6 — Production Grade
- [ ] FastAPI REST server wrapping the orchestrator
- [ ] Queue-based job processing (Celery + Redis)
- [ ] Containerised worker nodes (Docker)
- [ ] Distributed automation workers across multiple workstations
- [ ] Full audit trail: every action logged with screenshots to a database
- [ ] Project export: save ladder logic to FBD/IEC 61131-3 XML
- [ ] Plugin system: third-party tools registered via entry_points

### Phase 7 — AI Fine-Tuning
- [ ] Collect (user_description, ladder_program) pairs from production use
- [ ] Fine-tune a small model (e.g. Qwen-7B) on PLC-specific data
- [ ] Train a classification head to detect circuit types from descriptions
- [ ] Reward model for ladder logic correctness (simulation-based)
