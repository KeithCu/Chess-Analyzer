#!/usr/bin/env python3
"""
Chess Game Analysis Script

Analyzes a chess game between Stockfish and another engine to identify
critical mistakes that changed the course of the game.
"""

import argparse
import chess
import chess.pgn
import chess.engine
import io
import time
from typing import List, Optional

# Configuration globals
TIME_LIMIT = 11.0  # Seconds per engine call for move analysis
QUICK_ANALYSIS_TIME = 0.1  # Seconds per move for quick analysis of early moves
QUICK_ANALYSIS_PLY = 50  # Number of ply moves to use quick analysis (25 moves = 50 ply)
# PV (Principal Variation) is the best line of play the engine calculates - showing the sequence of moves
# the engine thinks is optimal.
TOP_N = 20  # Number of worst moves to display
GAME_OVER_EVAL_THRESHOLD = 10.0  # Evaluation threshold (pawns) to detect game over and use quick analysis
ANALYSIS_MODE = "stability"  # Analysis mode: "time" for fixed time limits, "stability" for stability-based stopping
STABILITY_THRESHOLD = 10.0  # Seconds of no changes to best move before stopping (stability mode only)


class GameAnalyzer:
    def __init__(self, stockfish_path: str = "/usr/bin/stockfish"):
        self.stockfish_path = stockfish_path
        self.engine = None

    def __enter__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
        self.engine.configure({"Hash": 8192, "Threads": 4})  # Adjust to hardware
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.engine:
            self.engine.quit()

    def load_game_from_pgn(self, pgn_string: str) -> chess.pgn.Game:
        """Load a game from PGN string."""
        pgn_io = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn_io)
        return game


    def analyze_game(self, game: chess.pgn.Game) -> List[dict]:
        """
        Single-pass analysis: analyze each position once and collect move data.
        
        Args:
            game: The chess game to analyze
            
        Returns:
            List of dictionaries with move analysis data
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized. Use with statement.")

        mainline_nodes = list(game.mainline())
        total_moves = len(mainline_nodes)
        
        if ANALYSIS_MODE == "stability":
            mode_info = f"stability mode (stable for {STABILITY_THRESHOLD}s)"
        else:
            mode_info = f"time mode (first {QUICK_ANALYSIS_PLY} ply: {QUICK_ANALYSIS_TIME}s, rest: {TIME_LIMIT}s per move)"
        
        print(f"\n=== Single Pass Analysis ({mode_info}) ===")
        print(f"Analyzing {total_moves} moves...\n")
        
        board = game.board()
        moves_analysis = []
        move_number = 1
        ply_index = 0
        
        # Initial position analysis (before the first move)
        current_analysis = self.analyze_position(board, QUICK_ANALYSIS_TIME)
        
        for node in mainline_nodes:
            player = "White" if board.turn == chess.WHITE else "Black"
            move = node.move
            san_move = board.san(move)
            pre_move_fen = board.fen()
            
            print(f"Analyzing: Move {move_number}. {player} {san_move} (ply {ply_index + 1}/{total_moves})...", flush=True)
            
            # Make the move
            board.push(move)
            
            eval_before = current_analysis['evaluation']
            
            # Use quick analysis for first 50 ply moves, or if game is already decided
            if ply_index + 1 < QUICK_ANALYSIS_PLY:
                time_limit = QUICK_ANALYSIS_TIME
            elif eval_before is not None and abs(eval_before) > GAME_OVER_EVAL_THRESHOLD:
                time_limit = QUICK_ANALYSIS_TIME
            else:
                time_limit = TIME_LIMIT
            
            # Analyze position AFTER move
            next_analysis = self.analyze_position(board, time_limit)
            eval_after = next_analysis['evaluation']
            
            eval_change = self._calculate_eval_change(eval_before, eval_after)
            
            move_data = {
                'move_number': move_number,
                'player': player,
                'move': move,
                'san': san_move,
                'eval_before': eval_before,
                'eval_after': eval_after,
                'eval_change': eval_change,
                'board_fen': board.fen(),
                'pre_move_fen': pre_move_fen,
                'ply_index': ply_index,
                'time_taken_before': current_analysis['time_taken'],
                'time_taken_after': next_analysis['time_taken'],
                'position_analysis': current_analysis
            }
            moves_analysis.append(move_data)
            
            # Update current analysis for next move
            current_analysis = next_analysis
            ply_index += 1
            
            if board.is_game_over():
                break
            
            if board.turn == chess.WHITE:
                move_number += 1
            
        return moves_analysis

    def _extract_evaluation(self, info: dict) -> Optional[float]:
        """Extract numerical evaluation from engine info."""
        if 'score' in info:
            score = info['score']
            if score.relative.is_mate():
                # Convert mate scores to capped positive/negative values
                mate_distance = score.relative.mate()
                if mate_distance > 0:
                    return min(99, 1000 - mate_distance)  # Cap at +99
                else:
                    return max(-99, -1000 + mate_distance)  # Cap at -99
            else:
                # Convert centipawns to pawns
                return score.relative.cp / 100.0
        return None

    def _calculate_eval_change(self, eval_before: Optional[float],
                              eval_after: Optional[float]) -> Optional[float]:
        """
        Calculate how much the evaluation changed after the move.
        Positive values mean the move improved the position.
        Negative values mean the move worsened the position.
        """
        if eval_before is None or eval_after is None:
            return None

        # Evaluations are relative to the side to move.
        # eval_before is from the perspective of the player making the move.
        # eval_after is from the perspective of the opponent.
        # To compare, we negate eval_after to convert it to the player's perspective.
        return (-eval_after) - eval_before

    def find_worst_moves(self, analysis: List[dict]) -> List[dict]:
        # Find all moves with valid evaluation changes
        # Also filter out moves when the game is already decided
        moves_with_change = [
            m for m in analysis 
            if m.get('eval_change') is not None and 
            (m.get('eval_before') is None or abs(m.get('eval_before')) <= GAME_OVER_EVAL_THRESHOLD)
        ]
        
        # Sort by evaluation change (most negative first)
        moves_with_change.sort(key=lambda x: x['eval_change'])
        
        return moves_with_change[:TOP_N]

    def analyze_position(self, board: chess.Board, time_limit: float) -> dict:
        """
        Get detailed analysis of a position including best move and principal variation.

        Args:
            board: Current board position
            time_limit: Time limit for analysis (used only in time-based mode)

        Returns:
            Dictionary with analysis results (including 'time_taken')
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized. Use with statement.")

        start_time = time.time()
        
        # Force time-based mode for quick analysis (early moves)
        use_stability = ANALYSIS_MODE == "stability" and time_limit != QUICK_ANALYSIS_TIME
        
        if use_stability:
            # Stability-based mode: stop when best move is stable for STABILITY_THRESHOLD seconds
            last_best_move = None
            last_change_time = start_time
            best_pv = None
            best_eval = None
            last_depth = 0
            
            # Use a very long time limit for the engine, but we'll stop early based on stability
            with self.engine.analysis(board, chess.engine.Limit(time=86400.0)) as analysis:
                for info in analysis:
                    current_pv = info.get("pv")
                    current_depth = info.get("depth", 0)
                    if not current_pv:
                        continue
                    
                    current_best_move = current_pv[0]
                    current_eval = self._extract_evaluation(info)
                    
                    # Check if best move changed
                    if current_best_move != last_best_move:
                        is_initial = last_best_move is None
                        last_best_move = current_best_move
                        last_change_time = time.time()
                        best_pv = list(current_pv)
                        best_eval = current_eval
                        last_depth = current_depth
                        
                        # Print when best move changes
                        elapsed = time.time() - start_time
                        eval_str = f"{current_eval:+.2f}" if current_eval is not None else "None"
                        
                        # Format PV for display
                        temp_board = board.copy()
                        san_moves = []
                        for m in current_pv[:7]:
                            try:
                                san_moves.append(temp_board.san(m))
                                temp_board.push(m)
                            except:
                                san_moves.append(str(m))
                        pv_str = " ".join(san_moves)
                        
                        if is_initial:
                            print(f"    [{elapsed:6.1f}s] Best variation (depth {current_depth}): Eval {eval_str}")
                            print(f"    PV: {pv_str}")
                        else:
                            try:
                                best_move_san = board.san(current_best_move)
                            except:
                                best_move_san = str(current_best_move)
                            print(f"    [{elapsed:6.1f}s] Best move CHANGED to {best_move_san} (depth {current_depth}): Eval {eval_str}")
                            print(f"    PV: {pv_str}")
                    else:
                        # Best move unchanged, check if we've been stable long enough
                        current_time = time.time()
                        stability_elapsed = current_time - last_change_time
                        if stability_elapsed >= STABILITY_THRESHOLD:
                            # Stable for threshold duration, stop analysis
                            elapsed = time.time() - start_time
                            print(f"    [{elapsed:6.1f}s] ✓ Stable for {STABILITY_THRESHOLD}s - moving to next move")
                            break
                        # Update PV and eval even if best move hasn't changed (refinement)
                        best_pv = list(current_pv)
                        best_eval = current_eval
                        last_depth = current_depth
            
            end_time = time.time()
            
            analysis_result = {
                'best_move': last_best_move,
                'evaluation': best_eval,
                'principal_variation': best_pv[:7] if best_pv else [],
                'time_taken': end_time - start_time
            }
        else:
            # Time-based mode: use fixed time limit
            info = self.engine.analyse(board, chess.engine.Limit(time=time_limit),
                                     multipv=1, info=chess.engine.INFO_ALL)
            end_time = time.time()

            analysis_result = {
                'best_move': None,
                'evaluation': None,
                'principal_variation': [],
                'time_taken': end_time - start_time
            }

            if info:
                info = info[0] if isinstance(info, list) else info

                if 'pv' in info and info['pv']:
                    analysis_result['best_move'] = info['pv'][0]
                    analysis_result['principal_variation'] = info['pv'][:7]  # First 7 moves of PV

                if 'score' in info:
                    analysis_result['evaluation'] = self._extract_evaluation(info)

        return analysis_result

    def analyze_specific_move(self, board: chess.Board, duration_seconds: float, actual_move: Optional[chess.Move] = None):
        """
        Analyze a specific position, reporting when the best variation changes.
        Uses time-based or stability-based mode depending on ANALYSIS_MODE global.
        
        Args:
            board: The position to analyze
            duration_seconds: How long to analyze (used only in time-based mode)
            actual_move: Optional move that was actually played in the game (for comparison)
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized. Use with statement.")

        # Determine analysis mode and set up header
        if ANALYSIS_MODE == "stability":
            mode_str = f"stability mode (stable for {STABILITY_THRESHOLD}s)"
        else:
            mode_str = f"time mode ({duration_seconds}s)"
        
        print(f"\n=== Deep Analysis ({mode_str}) ===")
        print(f"Position FEN: {board.fen()}")
        print(f"Side to move: {'White' if board.turn == chess.WHITE else 'Black'}")
        if actual_move:
            try:
                actual_move_san = board.san(actual_move)
                print(f"Move played in game: {actual_move_san}")
            except:
                print(f"Move played in game: {actual_move}")
        print("-" * 60)
        
        # Evaluate the actual move if provided
        actual_move_eval = None
        if actual_move:
            try:
                test_board = board.copy()
                test_board.push(actual_move)
                actual_analysis = self.analyze_position(test_board, 10)  # Quick evaluation
                # The evaluation is from the opponent's perspective, so negate it
                # to compare with the PV evaluation (which is from current player's perspective)
                if actual_analysis['evaluation'] is not None:
                    actual_move_eval = -actual_analysis['evaluation']
            except:
                pass

        start_time = time.time()
        last_pv = None
        last_eval = None
        last_depth = 0
        last_best_move = None
        last_change_time = start_time  # Track when best move last changed (for stability mode)
        
        # Set up analysis limit based on mode
        if ANALYSIS_MODE == "stability":
            # Use a very long time limit, but we'll stop early based on stability
            analysis_limit = chess.engine.Limit(time=86400.0)
        else:
            # Time-based mode: use the provided duration
            analysis_limit = chess.engine.Limit(time=duration_seconds)
        
        # Use AnalysisResult as a context manager for streaming
        with self.engine.analysis(board, analysis_limit) as analysis:
            for info in analysis:
                current_pv = info.get("pv")
                current_eval = self._extract_evaluation(info)
                current_depth = info.get("depth", 0)
                
                if not current_pv:
                    continue
                
                display_pv = current_pv
                
                # A meaningful change is when the best move (first move) changes, or it's the initial variation.
                # We skip printing when the variation is refined but the first move stays the same.
                current_best_move = display_pv[0]
                best_move_changed = last_pv is None or current_best_move != last_best_move
                
                if best_move_changed:
                    elapsed = time.time() - start_time
                    eval_str = f"{current_eval:+.2f}" if current_eval is not None else "None"
                    
                    # Store the displayed PV for future comparison
                    last_pv = list(display_pv)
                    last_change_time = time.time()  # Update change time when best move changes
                    
                    # Correctly format PV for display
                    temp_board = board.copy()
                    
                    try:
                        best_move_san = temp_board.san(current_best_move)
                    except:
                        best_move_san = str(current_best_move)

                    san_moves = []
                    for m in display_pv:
                        try:
                            san_moves.append(temp_board.san(m))
                            temp_board.push(m)
                        except:
                            san_moves.append(str(m))
                    pv_str = " ".join(san_moves)
                    
                    if last_depth == 0:
                        print(f"[{elapsed:6.1f}s] Initial best variation (depth {current_depth}):")
                    else:
                        print(f"[{elapsed:6.1f}s] Best move CHANGED to {best_move_san} (depth {current_depth}):")
                        
                    print(f"          Eval: {eval_str}")
                    if actual_move_eval is not None and current_eval is not None:
                        eval_diff = current_eval - actual_move_eval
                        if eval_diff > 0:
                            print(f"          PV advantage over move played: +{eval_diff:.2f} pawns")
                        elif eval_diff < 0:
                            print(f"          PV advantage over move played: {eval_diff:.2f} pawns")
                        else:
                            print(f"          PV advantage over move played: 0.00 pawns (equal)")
                    print(f"          PV  : {pv_str}")
                    
                    last_eval = current_eval
                    last_depth = current_depth
                    last_best_move = current_best_move
                else:
                    # Update tracking variables even when we don't print
                    last_pv = list(display_pv)
                    last_eval = current_eval
                    last_depth = current_depth
                    last_best_move = current_best_move
                    
                    # In stability mode, check if we've been stable long enough
                    if ANALYSIS_MODE == "stability":
                        current_time = time.time()
                        if (current_time - last_change_time) >= STABILITY_THRESHOLD:
                            # Stable for threshold duration, stop analysis
                            elapsed = time.time() - start_time
                            print(f"[{elapsed:6.1f}s] Best move stable for {STABILITY_THRESHOLD}s - stopping analysis")
                            break
                
                # Stop if we've exceeded time (time-based mode only)
                if ANALYSIS_MODE == "time" and time.time() - start_time > duration_seconds:
                    break

        print("-" * 60)
        elapsed_total = time.time() - start_time
        if ANALYSIS_MODE == "stability":
            print(f"Analysis complete after {elapsed_total:.1f}s (best move stable for {STABILITY_THRESHOLD}s)")
        else:
            print(f"Analysis complete after {elapsed_total:.1f}s")
        if last_pv:
            temp_board = board.copy()
            san_moves = []
            for m in last_pv[:7]:
                try:
                    san_moves.append(temp_board.san(m))
                    temp_board.push(m)
                except:
                    san_moves.append(str(m))
            pv_str = " ".join(san_moves)
            print(f"Final best variation: {pv_str} (Eval: {last_eval:+.2f})")
            if actual_move_eval is not None and last_eval is not None:
                eval_diff = last_eval - actual_move_eval
                if eval_diff > 0:
                    print(f"PV advantage over move played: +{eval_diff:.2f} pawns")
                elif eval_diff < 0:
                    print(f"PV advantage over move played: {eval_diff:.2f} pawns")
                else:
                    print(f"PV advantage over move played: 0.00 pawns (equal)")

    def print_worst_moves_report(self, game: chess.pgn.Game, worst_moves: List[dict]):
        """Print a report focusing on the worst moves with detailed analysis."""
        print("Chess Game Analysis: Worst Moves Against Stockfish")
        print("=" * 60)
        print()

        print("Game Summary:")
        print(f"White: {game.headers.get('White', 'Unknown')}")
        print(f"Black: {game.headers.get('Black', 'Unknown')}")
        print(f"Result: {game.headers.get('Result', 'Unknown')}")
        print()

        print("TOP MOVES WITH LARGEST EVALUATION DROPS:")
        print("-" * 50)

        for i, move_data in enumerate(worst_moves, 1):
            move_num = move_data['move_number']
            player = move_data['player']
            move = move_data['move']
            move_str = move_data.get('san', str(move))
            eval_change = move_data['eval_change']
            position_analysis = move_data['position_analysis']

            # In one-pass, total time spent to evaluate this move's swing
            total_time = move_data['time_taken_before'] + move_data['time_taken_after']
            print(f"{i}. Move {move_num:2d}. {player:5s} played {move_str}")
            print(f"   Evaluation change: {eval_change:+.2f} pawns (Analysis time: {total_time:.1f}s)")
            
            if position_analysis['best_move']:
                print(f"   Stockfish preferred: {position_analysis['best_move']}")
                if position_analysis['principal_variation']:
                    pv_str = " ".join(str(m) for m in position_analysis['principal_variation'])
                    print(f"   Better continuation: {pv_str}")

            if abs(eval_change) > 100:  # Mate scores
                print("   📝 NOTE: When game is already won/lost, large score changes are expected")
                print("   Focus on earlier moves for meaningful mistakes")
            elif eval_change < -3.0:
                print("   ⚠️  SERIOUS MISTAKE: Large evaluation drop indicates major error")
            elif eval_change < -1.0:
                print("   ⚠️  MISTAKE: Position significantly worsened")

            print()

        # Overall game assessment
        print("GAME ASSESSMENT:")
        print("-" * 20)
        if worst_moves:
            worst = worst_moves[0]
            worst_move_str = worst.get('san', str(worst['move']))
            print(f"🎯 Largest swing: Move {worst['move_number']}. {worst['player']} played {worst_move_str}")
            print(f"   Evaluation dropped by {worst['eval_change']:+.2f} pawns")
        else:
            print("No decisive mistakes detected within the configured thresholds.")
        print("📝 Note: Large evaluation changes in already won/lost positions carry less insight.")
        print("   Focus on the earliest large drops to understand where the game turned.")
        print()

        print("Analysis Notes:")
        print("- Evaluation change shows how much worse the position became after the move")
        print("- Positive values mean the move improved the position")
        print("- The 'best line' shows what Stockfish thought was the correct continuation")
        print()
        # Note: This is only the time for worst moves + positions. 
        # The full scan time isn't tracked here easily without passing more data.
        print(f"Total time spent on top critical moves analysis: {sum(m['time_taken_before'] + m['time_taken_after'] for m in worst_moves):.1f}s")
        print()


def main():
    """Run the analysis for the provided PGN (file or built-in sample)."""

    parser = argparse.ArgumentParser(description="Analyze a chess PGN for decisive mistakes.")
    parser.add_argument("pgn_file", nargs="?", help="Path to the PGN file to analyze.")
    parser.add_argument("--debug", action="store_true",
                        help="Print per-move evaluations to help diagnose analysis output.")
    parser.add_argument("--analyze-move", type=int, help="Specific move number to analyze deeply.")
    parser.add_argument("--color", choices=["white", "black"], default="white", 
                        help="Color to analyze for the specified move (default: white).")
    parser.add_argument("--duration", type=float, default=240.0, 
                        help="Duration in seconds for move analysis (default: 240.0).")
    args = parser.parse_args()

    if args.pgn_file:
        with open(args.pgn_file, "r", encoding="utf-8") as pgn_file:
            pgn_game = pgn_file.read()
    else:
        pgn_game = '''[Event "Local Event"]
[Site "Local Site"]
[Date "2025.11.22"]
[Round "1"]
[White "Stockfish 17.1"]
[Black "PyChess.py"]
[Result "1-0"]
[PlyCount "55"]
[Termination "normal"]
[WhiteClock "0:04:55.127"]
[BlackClock "0:09:40.767"]
[TimeControl "300+30"]
[FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]
[ECO "D15"]
[Opening "Slav Defense"]
[Variation "Chameleon Variation"]

1. d4 d5 2. c4 c6 3. Nf3 Nf6 4. Nc3 a6 5. e3 Bf5 6. Ne5 Nbd7 7. Qb3 Qc7 8. cxd5
Nxe5 9. dxe5 Nxd5 10. Nxd5 cxd5 11. Bd2 Qxe5 12. Be2 O-O-O 13. Rc1+ Kb8 14. Bxa6
Rd7 15. O-O Ka7 16. Bxb7 Rxb7 17. Qa4+ Kb8 18. Qe8+ Ka7 19. Qa4+ Kb8 20. Bc3 Qd6
21. Qe8+ Bc8 22. Be5 Ka7 23. Bxd6 exd6 24. Rxc8 Rxb2 25. Qd7+ Ka6 26. Qc6+ Ka5
27. Ra8+ Kb4 28. Ra4# 1-0
'''

    with GameAnalyzer() as analyzer:
        # Load the game
        game = analyzer.load_game_from_pgn(pgn_game)

        if args.analyze_move:
            print(f"Deeply analyzing move {args.analyze_move} for {args.color}...")
            board = game.board()
            target_ply = (args.analyze_move - 1) * 2
            if args.color == "black":
                target_ply += 1
            
            # Advance board to the target position
            mainline = list(game.mainline())
            if target_ply > len(mainline):
                print(f"Error: Move {args.analyze_move} {args.color} is beyond the end of the game.")
                return

            for i in range(target_ply):
                board.push(mainline[i].move)
            
            # Get the actual move that was played from this position
            actual_move = mainline[target_ply].move if target_ply < len(mainline) else None
            
            analyzer.analyze_specific_move(board, args.duration, actual_move)
            return

        print("Analyzing full game...")
        print(f"White: {game.headers.get('White', 'Unknown')}")
        print(f"Black: {game.headers.get('Black', 'Unknown')}")
        print()

        # Analyze all moves
        analysis = analyzer.analyze_game(game)

        if args.debug:
            print("DEBUG: Per-move evaluation details")
            print("-" * 60)
            print(f"{'Move':>4s} {'Ply':>3s} {'Player':>5s} {'Move':>8s} "
                  f"{'EvalBefore':>12s} {'EvalAfter':>12s} {'ΔEval':>8s}")
            for move in analysis:
                eval_before = move.get('eval_before')
                eval_after = move.get('eval_after')
                eval_change = move.get('eval_change')
                eval_before_str = f"{eval_before:+.2f}" if eval_before is not None else "None"
                eval_after_str = f"{eval_after:+.2f}" if eval_after is not None else "None"
                eval_change_str = f"{eval_change:+.2f}" if eval_change is not None else "None"
                print(f"{move['move_number']:4d} {move['ply_index']:3d} "
                      f"{move['player'][:5]:>5s} {str(move['move']):>8s} "
                      f"{eval_before_str:>12s} {eval_after_str:>12s} "
                      f"{eval_change_str:>8s}")
            print("-" * 60)

        # Find worst moves
        worst_moves = analyzer.find_worst_moves(analysis)

        # Print report
        analyzer.print_worst_moves_report(game, worst_moves)


if __name__ == "__main__":
    main()
