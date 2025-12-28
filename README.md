# ♟️ Chess Game Analysis Tool

A powerful Python tool for analyzing chess games using Stockfish, with support for both time-based and stability-based analysis modes.

```
    ╔═══════════════════════════════════════════════════╗
    ║                                                   ║
    ║   ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜   Chess Game Analyzer         ║
    ║   ♟ ♟ ♟ ♟ ♟ ♟ ♟ ♟   Powered by Stockfish        ║
    ║                                                   ║
    ║   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   ║
    ║                                                   ║
    ║   Analyze games • Find mistakes • Deep analysis   ║
    ║                                                   ║
    ╚═══════════════════════════════════════════════════╝
```

## 🚀 Quick Start

### Prerequisites

- Python 3.x
- Stockfish engine (expected at `/usr/bin/stockfish` by default)
- `python-chess` library

### Installation

1. Clone this repository:
   ```bash
   git clone <your-repo-url>
   cd Chess
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/Mac
   # or
   .venv\Scripts\activate  # On Windows
   ```

3. Install dependencies:
   ```bash
   pip install python-chess
   ```

### Basic Usage

```bash
python analyze_game.py <pgn_file>
```

**Example:**
```bash
python analyze_game.py alphazero-stockfish.pgn
```

## 📋 Features

- ✅ **Dual Analysis Modes**
  - **Time Mode**: Fixed time limits per move for predictable analysis duration
  - **Stability Mode**: Continues until best move is stable, ensuring accurate results

- ✅ **Smart Analysis**
  - Quick analysis for early game moves (first 50 ply)
  - Automatic quick analysis for won/lost positions
  - Detailed Principal Variation (PV) reporting

- ✅ **Progress Tracking**
  - Real-time progress output in stability mode
  - Shows best move changes, evaluations, and depth
  - Visual indicators when stability is reached

- ✅ **Deep Move Analysis**
  - Analyze specific moves in detail
  - Compare played moves with engine recommendations
  - Detailed evaluation reports

## 🎛️ Configuration

Edit the configuration globals at the top of `analyze_game.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANALYSIS_MODE` | `"stability"` | Analysis mode: `"time"` or `"stability"` |
| `TIME_LIMIT` | `11.0` | Standard move analysis time (seconds, time mode only) |
| `QUICK_ANALYSIS_TIME` | `0.1` | Time for early game moves (seconds) |
| `QUICK_ANALYSIS_PLY` | `50` | Number of ply moves to use quick analysis |
| `STABILITY_THRESHOLD` | `10.0` | Seconds of stability required (stability mode only) |
| `TOP_N` | `20` | Number of worst moves to display |
| `GAME_OVER_EVAL_THRESHOLD` | `10.0` | Evaluation threshold for quick analysis (pawns) |

## 📖 Usage Examples

### Basic Analysis
```bash
python analyze_game.py alphazero-stockfish.pgn
```

### Debug Mode (Detailed Per-Move Table)
```bash
python analyze_game.py alphazero-stockfish.pgn --debug
```

### Deep Analysis of Specific Move
```bash
# Analyze move 10 for white
python analyze_game.py alphazero-stockfish.pgn --analyze-move 10 --color white

# Analyze move 15 for black with custom duration
python analyze_game.py alphazero-stockfish.pgn --analyze-move 15 --color black --duration 300
```

## 🔍 How It Works

### Analysis Modes

#### Time Mode
- Uses fixed time limits per move
- Predictable analysis duration
- Best for batch processing or time-constrained analysis

#### Stability Mode (Recommended)
- Continues analyzing until the best move remains unchanged for the stability threshold
- Ensures accurate results by waiting for engine convergence
- Shows real-time progress with best variation updates
- Automatically stops when stability is reached

### Analysis Flow

```
┌─────────────────────────────────────────────────┐
│  Load PGN Game                                  │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│  Early Moves (first 50 ply)                    │
│  → Quick Analysis (0.1s)                        │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│  Later Moves                                    │
│  → Time Mode: Fixed time limit                  │
│  → Stability Mode: Until stable                 │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│  Identify Worst Moves                           │
│  → Calculate evaluation changes                 │
│  → Sort by largest drops                        │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│  Generate Report                                 │
│  → Top N worst moves                            │
│  → Principal variations                         │
│  → Evaluation analysis                          │
└─────────────────────────────────────────────────┘
```

## 📊 Output Example

```
=== Single Pass Analysis (stability mode (stable for 10.0s)) ===
Analyzing 111 moves...

Analyzing: Move 28. Black Qe7 (ply 56/111)...
    [   0.0s] Best variation (depth 1): Eval +0.60
    PV: Rg1 Rg8
    [   0.0s] Best move CHANGED to h4 (depth 3): Eval +0.59
    PV: h4 Rg8 h5
    [  23.1s] Best move CHANGED to Rg1 (depth 40): Eval +0.89
    PV: Rg1
    [  33.8s] ✓ Stable for 10.0s - moving to next move

TOP MOVES WITH LARGEST EVALUATION DROPS:
--------------------------------------------------
1. Move 15. Black played Qd6
   Evaluation change: -2.45 pawns (Analysis time: 45.2s)
   Stockfish preferred: Qc7
   Better continuation: Qc7 e4 d5 ...
```

## 🛠️ Command Line Options

| Option | Description |
|--------|-------------|
| `pgn_file` | Path to PGN file to analyze (optional, uses built-in sample if omitted) |
| `--debug` | Print detailed per-move evaluation table |
| `--analyze-move N` | Deeply analyze specific move number |
| `--color white\|black` | Color to analyze (for `--analyze-move`, default: white) |
| `--duration SECONDS` | Duration for move analysis (default: 240.0) |

## 📝 Notes

- Early moves (first 50 ply) always use quick analysis regardless of mode for efficiency
- Won/lost positions (evaluation > 10.0 pawns) automatically use quick analysis
- Stability mode provides the most accurate results but may take longer
- The tool tracks evaluation changes to identify critical mistakes

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📄 License

This project is licensed under the **GNU Lesser General Public License v2.1 (LGPL-2.1)**.

```
Copyright (C) 2025

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
```

For the full license text, see [LICENSE](LICENSE) file.

## 🔗 Related

- [python-chess](https://github.com/niklasf/python-chess) - Python chess library
- [Stockfish](https://stockfishchess.org/) - Strong open-source chess engine

---

**Made with ♟️ for chess analysis**
