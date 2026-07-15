#!/usr/bin/env python3
from __future__ import annotations

import sys
import time
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import chess

# Constants
MATE_SCORE = 30000
INF = 10**9

PIECE_VALUES_MG = {
    chess.PAWN: 82,
    chess.KNIGHT: 337,
    chess.BISHOP: 365,
    chess.ROOK: 477,
    chess.QUEEN: 1025,
    chess.KING: 0,
}

PIECE_VALUES_EG = {
    chess.PAWN: 94,
    chess.KNIGHT: 281,
    chess.BISHOP: 297,
    chess.ROOK: 512,
    chess.QUEEN: 936,
    chess.KING: 0,
}

# Piece-Square Tables (White perspective, mirrored for Black)
PST_PAWN_MG = [
    0,   0,   0,   0,   0,   0,   0,   0,
   50,  50,  50,  50,  50,  50,  50,  50,
   10,  10,  20,  30,  30,  20,  10,  10,
    5,   5,  10,  25,  25,  10,   5,   5,
    0,   0,   0,  20,  20,   0,   0,   0,
    5,  -5, -10,   0,   0, -10,  -5,   5,
    5,  10,  10, -20, -20,  10,  10,   5,
    0,   0,   0,   0,   0,   0,   0,   0,
]
PST_PAWN_EG = PST_PAWN_MG

PST_KNIGHT = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]

PST_BISHOP = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

PST_ROOK = [
     0,   0,   0,   5,   5,   0,   0,   0,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
     5,  10,  10,  10,  10,  10,  10,   5,
     0,   0,   0,   0,   0,   0,   0,   0,
]

PST_QUEEN = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   5,   0, -10,
    -10,   0,   5,   5,   5,   5,   5, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
]

PST_KING_MG = [
     20,  30,  10,   0,   0,  10,  30,  20,
     20,  20,   0,   0,   0,   0,  20,  20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]

PST_KING_EG = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30,   0,  20,  30,  30,  20,   0, -30,
    -30,  10,  30,  40,  40,  30,  10, -30,
    -30,  10,  30,  40,  40,  30,  10, -30,
    -30,   0,  20,  30,  30,  20,   0, -30,
    -30, -10,   0,   0,   0,   0, -10, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]

TT_EXACT, TT_ALPHA, TT_BETA = 0, 1, 2

@dataclass
class TTEntry:
    depth: int
    score: int
    flag: int
    best_move: Optional[chess.Move]

class CERAFEngine:
    def __init__(self):
        self.tt: Dict[int, TTEntry] = {}
        self.killers: Dict[int, List[chess.Move]] = {}
        self.history: Dict[Tuple[int, int, Optional[int]], int] = {}
        
        self.nodes = 0
        self.start_time = 0.0
        self.max_time = 1.5
        self.stop = False

    def clear_tables(self):
        self.tt.clear()
        self.killers.clear()
        self.history.clear()

    def _game_phase_and_eval(self, board: chess.Board) -> Tuple[int, int]:
        """Calculates dynamic phase-based values (Tapered Evaluation)."""
        mg_white, mg_black = 0, 0
        eg_white, eg_black = 0, 0
        phase = 0

        phase_weights = {
            chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 1, 
            chess.ROOK: 2, chess.QUEEN: 4, chess.KING: 0
        }

        for square, piece in board.piece_map().items():
            sq_idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
            phase += phase_weights[piece.piece_type]

            # Base material values
            mg_val = PIECE_VALUES_MG[piece.piece_type]
            eg_val = PIECE_VALUES_EG[piece.piece_type]

            # PST assignments
            if piece.piece_type == chess.PAWN:
                mg_pst, eg_pst = PST_PAWN_MG[sq_idx], PST_PAWN_EG[sq_idx]
            elif piece.piece_type == chess.KNIGHT:
                mg_pst, eg_pst = PST_KNIGHT[sq_idx], PST_KNIGHT[sq_idx]
            elif piece.piece_type == chess.BISHOP:
                mg_pst, eg_pst = PST_BISHOP[sq_idx], PST_BISHOP[sq_idx]
            elif piece.piece_type == chess.ROOK:
                mg_pst, eg_pst = PST_ROOK[sq_idx], PST_ROOK[sq_idx]
            elif piece.piece_type == chess.QUEEN:
                mg_pst, eg_pst = PST_QUEEN[sq_idx], PST_QUEEN[sq_idx]
            else: # KING
                mg_pst, eg_pst = PST_KING_MG[sq_idx], PST_KING_EG[sq_idx]

            if piece.color == chess.WHITE:
                mg_white += mg_val + mg_pst
                eg_white += eg_val + eg_pst
            else:
                mg_black += mg_val + mg_pst
                eg_black += eg_val + eg_pst

        mg_score = mg_white - mg_black
        eg_score = eg_white - eg_black

        # Max phase is 24 (4 rooks, 4 knights, 4 bishops, 2 queens)
        phase = min(phase, 24)
        total_eval = ((mg_score * phase) + (eg_score * (24 - phase))) // 24
        return phase, total_eval

    def evaluate(self, board: chess.Board) -> int:
        if board.is_checkmate():
            return -MATE_SCORE
        if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves():
            return 0

        phase, score = self._game_phase_and_eval(board)

        # Center control factor
        for sq in [chess.D4, chess.E4, chess.D5, chess.E5]:
            score += (len(board.attackers(chess.WHITE, sq)) - len(board.attackers(chess.BLACK, sq))) * 6

        # Bishop pair bonuses
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2: score += 25
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2: score -= 25

        return score if board.turn == chess.WHITE else -score

    def score_move(self, board: chess.Board, move: chess.Move, ply: int, tt_move: Optional[chess.Move]) -> int:
        if tt_move and move == tt_move:
            return 600000

        score = 0
        if move.promotion:
            score += 40000 + PIECE_VALUES_MG.get(move.promotion, 0)

        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            cap_val = PIECE_VALUES_MG[captured.piece_type] if captured else 100 # Default Pawn value for En Passant
            mover_val = PIECE_VALUES_MG[board.piece_type_at(move.from_square)]
            score += 10000 + (cap_val * 10) - mover_val

        if board.gives_check(move):
            score += 2000

        killers = self.killers.get(ply, [])
        if move in killers:
            score += 5000

        hist_key = (move.from_square, move.to_square, move.promotion)
        score += self.history.get(hist_key, 0)
        return score

    def ordered_moves(self, board: chess.Board, ply: int, tt_move: Optional[chess.Move]) -> List[chess.Move]:
        moves = list(board.legal_moves)
        moves.sort(key=lambda mv: self.score_move(board, mv, ply, tt_move), reverse=True)
        return moves

    def _check_time(self) -> None:
        if self.nodes & 2047 == 0:
            if time.perf_counter() - self.start_time >= self.max_time:
                self.stop = True

    def quiescence(self, board: chess.Board, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        self._check_time()
        if self.stop: return 0

        stand_pat = self.evaluate(board)
        if stand_pat >= beta: return beta
        if stand_pat > alpha: alpha = stand_pat

        captures = [mv for mv in board.legal_moves if board.is_capture(mv)]
        captures.sort(key=lambda mv: self.score_move(board, mv, ply, None), reverse=True)

        for move in captures:
            board.push(move)
            score = -self.quiescence(board, -beta, -alpha, ply + 1)
            board.pop()

            if self.stop: return 0
            if score >= beta: return beta
            if score > alpha: alpha = score

        return alpha

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int, allow_null: bool = True) -> int:
        self.nodes += 1
        self._check_time()
        if self.stop: return 0

        # Adjust score mapping for early terminal nodes
        if board.is_checkmate(): return -MATE_SCORE + ply
        if board.is_stalemate() or board.is_insufficient_material() or board.is_fivefold_repetition(): return 0

        zobrist_key = board.zobrist_hash()
        tt_entry = self.tt.get(zobrist_key)
        tt_move = tt_entry.best_move if tt_entry else None

        if tt_entry and tt_entry.depth >= depth:
            if tt_entry.flag == TT_EXACT: return tt_entry.score
            if tt_entry.flag == TT_ALPHA and tt_entry.score <= alpha: return tt_entry.score
            if tt_entry.flag == TT_BETA and tt_entry.score >= beta: return tt_entry.score

        if depth <= 0:
            return self.quiescence(board, alpha, beta, ply)

        # Upgraded Optimization: Null Move Pruning (NMP)
        if allow_null and depth >= 3 and not board.is_check():
            # Basic sanity verification: ensure side to move has non-pawn material
            has_pieces = any(
                board.pieces(pt, board.turn) 
                for pt in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]
            )
            if has_pieces:
                board.push(chess.Move.null())
                null_score = -self.negamax(board, depth - 1 - 2, -beta, -beta + 1, ply + 1, allow_null=False)
                board.pop()
                if self.stop: return 0
                if null_score >= beta:
                    return beta

        best_score = -INF
        best_move = None
        moves = self.ordered_moves(board, ply, tt_move)
        
        if not moves:
            return -MATE_SCORE + ply if board.is_check() else 0

        local_flag = TT_ALPHA

        for move in moves:
            board.push(move)
            score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()

            if self.stop: return 0

            if score > best_score:
                best_score = score
                best_move = move

            if score > alpha:
                alpha = score
                local_flag = TT_EXACT

            if alpha >= beta:
                local_flag = TT_BETA
                if not board.is_capture(move):
                    hist_key = (move.from_square, move.to_square, move.promotion)
                    self.history[hist_key] = self.history.get(hist_key, 0) + depth * depth
                    killer_list = self.killers.setdefault(ply, [])
                    if move not in killer_list:
                        killer_list.insert(0, move)
                        del killer_list[2:]
                break

        if best_move is None and moves:
            best_move = moves[0]

        self.tt[zobrist_key] = TTEntry(depth=depth, score=best_score, flag=local_flag, best_move=best_move)
        return best_score

    def extract_pv(self, board: chess.Board, depth: int) -> List[str]:
        pv = []
        temp_board = board.copy(stack=False)
        for _ in range(depth):
            entry = self.tt.get(temp_board.zobrist_hash())
            if entry and entry.best_move and entry.best_move in temp_board.legal_moves:
                pv.append(entry.best_move.uci())
                temp_board.push(entry.best_move)
            else:
                break
        return pv

    def search(self, board: chess.Board, max_time: float, max_depth: int = 64) -> chess.Move:
        self.start_time = time.perf_counter()
        self.max_time = max(0.01, max_time)
        self.stop = False
        self.nodes = 0

        root_board = board.copy(stack=False)
        best_move = next(root_board.legal_moves, None)

        for depth in range(1, max_depth + 1):
            if self.stop:
                break

            self.negamax(root_board, depth, -INF, INF, 0)

            if self.stop:
                break

            # Pull reliable data from Transposition Table
            root_entry = self.tt.get(root_board.zobrist_hash())
            if root_entry and root_entry.best_move:
                best_move = root_entry.best_move
                score = root_entry.score
                elapsed = time.perf_counter() - self.start_time
                nps = int(self.nodes / max(elapsed, 0.001))
                pv_list = self.extract_pv(root_board, depth)
                pv_str = " ".join(pv_list)

                # Format centipawn/mate string output for UCI protocol standard
                if abs(score) >= MATE_SCORE - 100:
                    mate_in_plies = MATE_SCORE - abs(score)
                    mate_in_moves = (mate_in_plies + 1) // 2
                    score_str = f"mate {mate_in_moves if score > 0 else -mate_in_moves}"
                else:
                    score_str = f"cp {score}"

                print(f"info depth {depth} score {score_str} nodes {self.nodes} nps {nps} time {int(elapsed * 1000)} pv {pv_str}")
                sys.stdout.flush()

        return best_move

def uci_loop():
    engine = CERAFEngine()
    board = chess.Board()

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            tokens = line.strip().split()
            if not tokens:
                continue

            command = tokens[0]

            if command == "uci":
                print("id name CERAF Engine Upgraded")
                print("id author Engine Core Dev")
                print("uciok")
                sys.stdout.flush()

            elif command == "isready":
                print("readyok")
                sys.stdout.flush()

            elif command == "ucinewgame":
                engine.clear_tables()
                board = chess.Board()

            elif command == "position":
                # Syntax options: position startpos [moves ...] or position fen ... [moves ...]
                if len(tokens) > 1:
                    if tokens[1] == "startpos":
                        board = chess.Board()
                        move_start = 2
                    elif tokens[1] == "fen":
                        # Stitch structural FEN spaces back together
                        fen_parts = []
                        idx = 2
                        while idx < len(tokens) and tokens[idx] != "moves":
                            fen_parts.append(tokens[idx])
                            idx += 1
                        board = chess.Board(" ".join(fen_parts))
                        move_start = idx
                    else:
                        continue

                    if move_start < len(tokens) and tokens[move_start] == "moves":
                        for m_str in tokens[move_start + 1:]:
                            try:
                                board.push_uci(m_str)
                            except ValueError:
                                pass

            elif command == "go":
                # Dynamic clock limits allocation setup
                wtime = btime = winc = binc = None
                movestogo = None
                depth_limit = 64

                # Quick parameter mapping pass
                i = 1
                while i < len(tokens):
                    t = tokens[i]
                    if t == "wtime" and i + 1 < len(tokens): wtime = int(tokens[i+1])
                    elif t == "btime" and i + 1 < len(tokens): btime = int(tokens[i+1])
                    elif t == "winc" and i + 1 < len(tokens): winc = int(tokens[i+1])
                    elif t == "binc" and i + 1 < len(tokens): binc = int(tokens[i+1])
                    elif t == "movestogo" and i + 1 < len(tokens): movestogo = int(tokens[i+1])
                    elif t == "depth" and i + 1 < len(tokens): depth_limit = int(tokens[i+1])
                    i += 1

                # Calculate search budget allocation dynamically
                my_time = wtime if board.turn == chess.WHITE else btime
                my_inc = winc if board.turn == chess.WHITE else binc

                if my_time is not None:
                    moves_divisor = movestogo if movestogo else 30
                    allocated_time = my_time / moves_divisor
                    if my_inc is not None:
                        allocated_time += my_inc * 0.6
                    # Safe buffers configuration
                    search_time = max(0.05, min(allocated_time / 1000.0, my_time / 4000.0))
                else:
                    search_time = 2.0  # Safe engine fallback fallback

                best_move = engine.search(board, max_time=search_time, max_depth=depth_limit)
                if best_move:
                    print(f"bestmove {best_move.uci()}")
                else:
                    # Fallback structural protection
                    fallback = next(board.legal_moves, chess.Move.null())
                    print(f"bestmove {fallback.uci()}")
                sys.stdout.flush()

            elif command == "stop":
                engine.stop = True

            elif command == "quit":
                break

        except Exception as e:
            # Prevent unexpected crashes inside industrial GUIs by silently ignoring bad input strings
            print(f"info string Error encountered: {str(e)}")
            sys.stdout.flush()

if __name__ == "__main__":
    uci_loop()
