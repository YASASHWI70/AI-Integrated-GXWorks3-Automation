"""
main.py — PLC AI Automation System — Entry Point
=================================================

This is the top-level orchestrator.  It connects all four layers:

    User Input
        ↓
    [AI Layer]         InputParser → LadderGenerator
        ↓
    [Validation Layer] LadderValidator
        ↓
    [MCP Layer]        ToolExecutor (sequences of MCP tools)
        ↓
    [UI Automation]    GXWorks3Interface (pyautogui + OpenCV)
        ↓
    GX Works3

USAGE EXAMPLES:

    # Natural language
    python main.py --input "Create a start-stop motor circuit using X0, X1, Y0"

    # JSON shorthand
    python main.py --input '{"type":"start_stop","start":"X0","stop":"X1","output":"Y0"}'

    # JSON file
    python main.py --file examples/motor_circuit.json

    # PDF spec
    python main.py --file spec.pdf

    # Demo mode (no GX Works3 needed — runs mock validation only)
    python main.py --demo

MILESTONE 1 FLOW (what the MVP achieves):
    1. Open GX Works3
    2. Create a new project
    3. Open the ladder editor
    4. Insert a start-stop ladder rung
    5. Save the project
"""

import sys
import argparse
import logging
from loguru import logger

import config

# ──────────────────────────────────────────────────────────────
# LOGGING SETUP
# ──────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configure loguru to write to both console and a rotating log file."""
    logger.remove()     # Remove loguru's default handler

    # Console — coloured, concise
    logger.add(
        sys.stdout,
        level=config.LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File — detailed, rotating
    logger.add(
        config.LOG_FILE,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} — {message}",
        rotation=config.LOG_ROTATION,
        retention=config.LOG_RETENTION,
        encoding="utf-8",
    )

    # Bridge Python's standard logging to loguru
    logging.basicConfig(handlers=[_LoguruHandler()], level=0, force=True)


class _LoguruHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ──────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ──────────────────────────────────────────────────────────────

class PLCAutomationOrchestrator:
    """
    Top-level controller that wires the four layers together.

    Call run(user_input) to execute the full MVP pipeline:
        parse → generate → validate → automate → save
    """

    def __init__(self) -> None:
        from ai_layer.input_parser     import InputParser
        from ai_layer.ladder_generator import LadderGenerator
        from validation_layer.ladder_validator import LadderValidator
        from mcp_layer.tool_executor   import ToolExecutor

        self.input_parser      = InputParser()
        self.ladder_generator  = LadderGenerator()
        self.validator         = LadderValidator()
        self.executor          = ToolExecutor()

    def run(
        self,
        user_input:   str,
        project_name: str = "PLCAIProject",
        demo_mode:    bool = False,
    ) -> None:
        """
        Execute the full pipeline from user input to saved GX Works3 project.

        Args:
            user_input:   The user's request (text, JSON, or PDF path).
            project_name: Name for the new GX Works3 project.
            demo_mode:    If True, skip UI automation (validate only).
        """
        logger.info("=" * 60)
        logger.info("PLC AI Automation System — Starting pipeline")
        logger.info("=" * 60)

        # ── STEP 1: Parse input ───────────────────────────────
        logger.info("Step 1/5 — Parsing input …")
        parsed = self.input_parser.parse(user_input)

        # ── STEP 2: Generate ladder logic ─────────────────────
        logger.info("Step 2/5 — Generating ladder logic …")
        from models.ladder_logic import LadderProgram
        if isinstance(parsed, LadderProgram):
            program = parsed
            logger.info("  Using pre-parsed LadderProgram directly.")
        else:
            # parsed is a text description — feed to LLM/rule-based generator
            from parsers.nlp_parser import NLPParser
            nlp_intent = NLPParser().parse(parsed)
            program    = self.ladder_generator.generate(nlp_intent.enriched_prompt)

        logger.info(
            "  Generated program '%s' with %d rung(s).",
            program.name, len(program.rungs),
        )
        logger.debug("  Program JSON:\n%s", program.to_json())

        # ── STEP 3: Validate ──────────────────────────────────
        logger.info("Step 3/5 — Validating ladder logic …")
        val_result = self.validator.validate(program)
        logger.info("\n%s", val_result.summary())

        if not val_result.is_valid:
            logger.error("Validation FAILED — aborting automation.")
            logger.error(val_result.summary())
            sys.exit(1)

        if demo_mode:
            logger.info("Demo mode enabled — skipping UI automation.")
            logger.success("Pipeline complete (demo).")
            return

        # ── STEP 4: Automate GX Works3 ────────────────────────
        logger.info("Step 4/5 — Running UI automation sequence …")
        self._run_automation(program, project_name)

        # ── STEP 5: Save project ─────────────────────────────
        logger.info("Step 5/5 — Saving project …")
        save_result = self.executor.execute(
            "save_project",
            {"project_name": project_name},
        )
        if save_result.ok:
            logger.success("Project saved successfully!")
        else:
            logger.error("Save failed: %s", save_result.error)

        logger.info("=" * 60)
        logger.success("Pipeline complete!")
        logger.info("=" * 60)

    def _run_automation(self, program, project_name: str) -> None:
        """Build and execute the full MCP tool sequence for a ladder program."""
        from models.ladder_logic import ElementType

        steps = []

        # ── Open GX Works3 ────────────────────────────────────
        steps.append({"tool": "open_gxworks3"})

        # ── Create project ────────────────────────────────────
        steps.append({
            "tool": "create_project",
            "params": {"project_name": project_name},
        })

        # ── Open ladder editor ────────────────────────────────
        steps.append({"tool": "open_ladder_editor"})

        # ── Insert ladder elements rung by rung ───────────────
        for rung in program.rungs:
            logger.info("  Inserting rung %d: %s", rung.id, rung.comment or "")

            # Navigate to the start of this rung
            if rung.id > 1:
                steps.append({
                    "tool": "open_ladder_editor",   # go_to_new_rung is handled inside
                })

            for el in rung.elements:
                if el.type in (ElementType.CONTACT_NO, ElementType.CONTACT_NC):
                    steps.append({
                        "tool": "insert_contact",
                        "params": {
                            "address":         el.address,
                            "col":             el.position.col,
                            "row":             el.position.row,
                            "normally_closed": el.type == ElementType.CONTACT_NC,
                        },
                    })
                elif el.type in (
                    ElementType.COIL,
                    ElementType.COIL_SET,
                    ElementType.COIL_RESET,
                ):
                    steps.append({
                        "tool": "insert_coil",
                        "params": {
                            "address":   el.address,
                            "col":       el.position.col,
                            "row":       el.position.row,
                            "coil_type": el.type,
                        },
                    })
                else:
                    logger.warning(
                        "  Element type '%s' not yet automated (MVP). Skipping.",
                        el.type,
                    )

        # ── Execute all steps ─────────────────────────────────
        results = self.executor.execute_sequence(steps, stop_on_failure=True)

        # ── Report results ────────────────────────────────────
        passed = sum(1 for r in results if r.ok)
        failed = len(results) - passed
        logger.info(
            "Automation sequence: %d/%d steps succeeded.", passed, len(results)
        )
        if failed:
            logger.warning("%d step(s) failed.", failed)
            for r in results:
                if not r.ok:
                    logger.error("  ✗ %s: %s", r.tool_name, r.error)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="PLC AI Automation System for GX Works3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --input "Create a start-stop motor circuit for X0, X1, Y0"
  python main.py --input '{"type":"start_stop","start":"X0","stop":"X1","output":"Y0"}'
  python main.py --file examples/motor.json
  python main.py --demo --input "motor circuit"
        """,
    )
    p.add_argument(
        "--input", "-i",
        type=str,
        help="User input: natural language text or JSON string.",
    )
    p.add_argument(
        "--file", "-f",
        type=str,
        help="Path to a JSON or PDF input file.",
    )
    p.add_argument(
        "--project", "-p",
        type=str,
        default="PLCAIProject",
        help="GX Works3 project name (default: PLCAIProject).",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Demo mode: parse and validate only; skip UI automation.",
    )
    return p


def main() -> None:
    setup_logging()

    args = build_arg_parser().parse_args()

    # Determine input
    if args.file:
        user_input = args.file      # InputParser will detect .pdf or .json
    elif args.input:
        user_input = args.input
    else:
        # Interactive mode
        logger.info("No input provided — entering interactive mode.")
        user_input = input(
            "\nDescribe the ladder logic you want to generate\n"
            "(e.g. 'Create a start-stop motor circuit using X0, X1, Y0'):\n> "
        ).strip()
        if not user_input:
            logger.error("No input provided. Exiting.")
            sys.exit(1)

    orchestrator = PLCAutomationOrchestrator()
    orchestrator.run(
        user_input   = user_input,
        project_name = args.project,
        demo_mode    = args.demo,
    )


if __name__ == "__main__":
    main()
