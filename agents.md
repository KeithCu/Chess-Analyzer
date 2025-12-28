# Agent Guide

## Environment
- Project root: `/home/keithcu/Desktop/Python/Chess`
- Always activate the existing virtual environment before running anything:
  - `fish -c 'source .venv/bin/activate.fish; <command>'`
  - Stockfish is expected at `/usr/bin/stockfish`; adjust the `GameAnalyzer` constructor only if the user requests it.

## Running the Analyzer
- Basic usage: `python analyze_game.py <pgn_file>`
- Optional flags:
  - `--debug`: Prints a detailed per-move table of evaluations (useful for verifying swings).
  - `--analyze-move <N>`: Deeply analyze a specific move number (with optional `--color white|black` and `--duration <seconds>`).

## Configuration (Globals in `analyze_game.py`)
Fine-tune analysis by editing these constants at the top of the script:
- `ANALYSIS_MODE` ("time" or "stability"): Analysis mode selection. Default: "stability"
  - `"time"`: Fixed time limits per move
  - `"stability"`: Continues until best move is stable for `STABILITY_THRESHOLD` seconds
- `TIME_LIMIT` (11.0s): Standard move analysis time (time mode only).
- `QUICK_ANALYSIS_TIME` (0.1s): Time for early game moves (first 50 ply) and won/lost positions. Always used regardless of mode.
- `QUICK_ANALYSIS_PLY` (50): Number of ply moves to use quick analysis (25 moves = 50 ply).
- `STABILITY_THRESHOLD` (10.0s): Seconds of no changes to best move before stopping (stability mode only).
- `TOP_N` (20): Number of worst moves to display in the report.
- `GAME_OVER_EVAL_THRESHOLD` (10.0): Evaluation threshold (pawns) to detect game over and use quick analysis.

## Analysis Logic
The script uses a **single-pass analysis**:
- **Early Moves**: The first `QUICK_ANALYSIS_PLY` moves always use quick time-based analysis (`QUICK_ANALYSIS_TIME`) regardless of mode, for efficiency.
- **Later Moves**: 
  - **Time Mode**: Uses fixed time limits (`TIME_LIMIT` for standard moves, `QUICK_ANALYSIS_TIME` for won/lost positions).
  - **Stability Mode**: Continues analyzing until the best move remains unchanged for `STABILITY_THRESHOLD` seconds. Shows progress output with best variation, evaluation, and when stability is reached.
- The script identifies the `TOP_N` moves with the largest evaluation drops and reports them with Principal Variation (PV) information.

## Typical Workflow
1. Activate `.venv`.
2. Run `python analyze_game.py some_game.pgn`.
3. In stability mode, watch the progress output showing best move changes and when stability is reached.
4. Review the "TOP MOVES WITH LARGEST EVALUATION DROPS" report.
5. If results look strange, re-run with `--debug` to see the per-ply breakdown.
6. For deep analysis of specific moves, use `--analyze-move <N>` with optional `--color` and `--duration` flags.

## Cautions
- User does not want unrelated edits; keep changes focused.
- Prefer absolute paths when calling tools in this environment.
- Do not add new files beyond explicit requests.

