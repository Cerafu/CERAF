"""
CERAF engine_core.py
A browser-friendly chess engine for Pyodide + python-chess.

Features:
- Negamax with alpha-beta pruning
- Iterative deepening
- Quiescence search
- Transposition table
- Killer move and history heuristics
- Simple positional evaluation
- Optional browser "brain" memory multiplier
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import chess

MATE_SCORE = 30000
INF = 10**9

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables from White's perspective.
# Values are centipawns. Black uses mirrored squares.
PST_PAWN = [
      0,   0,   0,   0,   0,   0,   0,   0,
     50,  50,  50,  50,  50,  50,  50,  50,
     10,  10,  20,  30,  30,  20,  10,  10,
      5,   5,  10,  25,  25,  10,   5,   5,
      0,   0,   0,  20,  20,   0,   0,   0,
      5,  -5, -10,   0,   0, -10,  -5,   5,
      5,  10,  10, -20, -20,  10,  10,   5,
      0,   0,   0,   0,   0,   0,   0,   0,
]

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

PST_KING_MID = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
]

PST_KING_END = [
    -50, -30, -30, -30, -30, -30, -30, -50,
    -30, -10,   0,   0,   0,   0, -10, -30,
    -30,   0,  20,  30,  30,  20,   0, -30,
    -30,  10,  30,  40,  40,  30,  10, -30,
    -30,  10,  30,  40,  40,  30,  10, -30,
    -30,   0,  20,  30,  30,  20,   0, -30,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -50, -40, -30, -20, -20, -30, -40, -50,
]


def _mirror(square: int) -> int:
    return chess.square_mirror(square)


def _pst(piece_type: int, square: int, color: bool, endgame: bool) -> int:
    table = {
        chess.PAWN: PST_PAWN,
        chess.KNIGHT: PST_KNIGHT,
        chess.BISHOP: PST_BISHOP,
        chess.ROOK: PST_ROOK,
        chess.QUEEN: PST_QUEEN,
        chess.KING: PST_KING_END if endgame else PST_KING_MID,
    }[piece_type]
    idx = square if color == chess.WHITE else _mirror(square)
    val = table[idx]
    return val


def _safe_brain_multiplier(brain: Any, board: chess.Board) -> float:
    if brain is None:
        return 1.0
    getter = getattr(brain, "get_multiplier", None)
    if not callable(getter):
        return 1.0
    try:
        mult = float(getter(board.epd()))
    except Exception:
        return 1.0
    if not math.isfinite(mult):
        return 1.0
    return max(0.25, min(1.75, mult))


def _game_phase(board: chess.Board) -> float:
    """0.0 = endgame, 1.0 = middlegame."""
    phase = 0
    for pt, weight in (
        (chess.QUEEN, 4),
        (chess.ROOK, 2),
        (chess.BISHOP, 1),
        (chess.KNIGHT, 1),
    ):
        phase += weight * (len(board.pieces(pt, chess.WHITE)) + len(board.pieces(pt, chess.BLACK)))
    return max(0.0, min(1.0, phase / 24.0))


def _material_count(board: chess.Board) -> int:
    total = 0
    for pt, val in PIECE_VALUES.items():
        if pt == chess.KING:
            continue
        total += val * (len(board.pieces(pt, chess.WHITE)) + len(board.pieces(pt, chess.BLACK)))
    return total


@dataclass
class TTEntry:
    depth: int
    score: int
    flag: int
    best_move: Optional[chess.Move]


TT_EXACT = 0
TT_ALPHA = 1
TT_BETA = 2


class CERAFEngine:
    def __init__(self, brain: Any = None):
        self.brain = brain
        self.tt: Dict[str, TTEntry] = {}
        self.killers: Dict[int, List[chess.Move]] = {}
        self.history: Dict[Tuple[int, int, Optional[int]], int] = {}

        self.nodes = 0
        self.start_time = 0.0
        self.max_time = 1.5
        self.stop = False
        self.last_info: Dict[str, Any] = {}

    # ---------- Evaluation ----------

    def evaluate(self, board: chess.Board) -> int:
        if board.is_checkmate():
            return -MATE_SCORE
        if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves():
            return 0

        score = 0
        endgame = _material_count(board) <= 2800
        phase = _game_phase(board)

        # Material + piece square tables
        for square, piece in board.piece_map().items():
            val = PIECE_VALUES[piece.piece_type]
            pst_bonus = _pst(piece.piece_type, square, piece.color, endgame)
            if piece.color == chess.WHITE:
                score += val + pst_bonus
            else:
                score -= val + pst_bonus

        # Mobility
        side_to_move = board.turn
        moves_now = board.legal_moves.count()
        board.turn = not side_to_move
        opp_moves = board.legal_moves.count()
        board.turn = side_to_move
        score += (moves_now - opp_moves) * 4

        # Center control
        for sq in [chess.D4, chess.E4, chess.D5, chess.E5]:
            attackers_w = len(board.attackers(chess.WHITE, sq))
            attackers_b = len(board.attackers(chess.BLACK, sq))
            score += (attackers_w - attackers_b) * 8

        # Bishop pair
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += 30
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= 30

        # Passed pawns
        for color in (chess.WHITE, chess.BLACK):
            pawns = board.pieces(chess.PAWN, color)
            enemy_pawns = board.pieces(chess.PAWN, not color)
            for sq in pawns:
                file_ = chess.square_file(sq)
                rank = chess.square_rank(sq)
                passed = True
                for ep in enemy_pawns:
                    ef = chess.square_file(ep)
                    er = chess.square_rank(ep)
                    if abs(ef - file_) <= 1:
                        if color == chess.WHITE and er > rank:
                            passed = False
                            break
                        if color == chess.BLACK and er < rank:
                            passed = False
                            break
                if passed:
                    advance = rank if color == chess.WHITE else 7 - rank
                    bonus = 12 + advance * 10
                    score += bonus if color == chess.WHITE else -bonus

        # King safety (simple)
        for color in (chess.WHITE, chess.BLACK):
            king_sq = board.king(color)
            if king_sq is None:
                continue
            shields = 0
            f = chess.square_file(king_sq)
            r = chess.square_rank(king_sq)
            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    nf, nr = f + df, r + dr
                    if 0 <= nf < 8 and 0 <= nr < 8:
                        sq = chess.square(nf, nr)
                        p = board.piece_at(sq)
                        if p and p.color == color and p.piece_type == chess.PAWN:
                            shields += 1
            score += (shields * 8) if color == chess.WHITE else -(shields * 8)

        # Endgame king activity
        if endgame:
            wk = board.king(chess.WHITE)
            bk = board.king(chess.BLACK)
            if wk is not None:
                score += (7 - abs(3.5 - chess.square_file(wk)) - abs(3.5 - chess.square_rank(wk))) * 6
            if bk is not None:
                score -= (7 - abs(3.5 - chess.square_file(bk)) - abs(3.5 - chess.square_rank(bk))) * 6

        # Blend by phase slightly so middlegame PST matters more than endgame PST
        score = int(score * (0.80 + phase * 0.20))

        # Apply browser "brain" memory multiplier
        mult = _safe_brain_multiplier(self.brain, board)
        score = int(score * mult)

        return score if board.turn == chess.WHITE else -score

    # ---------- Move ordering ----------

    def mvv_lva(self, board: chess.Board, move: chess.Move) -> int:
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured is None and board.is_en_passant(move):
                captured_value = PIECE_VALUES[chess.PAWN]
            elif captured is not None:
                captured_value = PIECE_VALUES[captured.piece_type]
            else:
                captured_value = 0
            mover = board.piece_at(move.from_square)
            mover_value = PIECE_VALUES[mover.piece_type] if mover else 0
            return 10000 + captured_value * 10 - mover_value
        return 0

    def score_move(self, board: chess.Board, move: chess.Move, ply: int, tt_move: Optional[chess.Move]) -> int:
        score = 0

        if tt_move is not None and move == tt_move:
            return 500000

        if move.promotion:
            score += 20000 + PIECE_VALUES.get(move.promotion, 0)

        if board.is_capture(move):
            score += self.mvv_lva(board, move)

        if board.gives_check(move):
            score += 3000

        killers = self.killers.get(ply, [])
        if move in killers:
            score += 8000

        hist_key = (move.from_square, move.to_square, move.promotion)
        score += self.history.get(hist_key, 0)
        return score

    def ordered_moves(self, board: chess.Board, ply: int, tt_move: Optional[chess.Move]) -> List[chess.Move]:
        moves = list(board.legal_moves)
        moves.sort(key=lambda mv: self.score_move(board, mv, ply, tt_move), reverse=True)
        return moves

    # ---------- Search ----------

    def _time_up(self) -> None:
        if self.nodes & 2047 == 0:
            if time.perf_counter() - self.start_time >= self.max_time:
                self.stop = True

    def quiescence(self, board: chess.Board, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        self._time_up()
        if self.stop:
            return 0

        stand_pat = self.evaluate(board)

        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        captures = [mv for mv in board.legal_moves if board.is_capture(mv) or board.gives_check(mv)]
        captures.sort(key=lambda mv: self.score_move(board, mv, ply, None), reverse=True)

        for move in captures:
            board.push(move)
            score = -self.quiescence(board, -beta, -alpha, ply + 1)
            board.pop()

            if self.stop:
                return 0
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        self._time_up()
        if self.stop:
            return 0

        if board.is_checkmate():
            return -MATE_SCORE + ply
        if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves():
            return 0

        fen_key = board.fen()
        tt_entry = self.tt.get(fen_key)
        tt_move = tt_entry.best_move if tt_entry else None
        original_alpha = alpha

        if tt_entry is not None and tt_entry.depth >= depth:
            if tt_entry.flag == TT_EXACT:
                return tt_entry.score
            if tt_entry.flag == TT_ALPHA and tt_entry.score <= alpha:
                return tt_entry.score
            if tt_entry.flag == TT_BETA and tt_entry.score >= beta:
                return tt_entry.score

        if depth <= 0:
            return self.quiescence(board, alpha, beta, ply)

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

            if self.stop:
                return 0

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

        if best_move is None:
            best_move = moves[0]

        self.tt[fen_key] = TTEntry(depth=depth, score=best_score, flag=local_flag, best_move=best_move)
        return best_score

    def search(self, board: chess.Board, max_time: float = 1.5, max_depth: int = 10) -> Optional[chess.Move]:
        self.start_time = time.perf_counter()
        self.max_time = max(0.05, float(max_time))
        self.stop = False
        self.nodes = 0
        self.last_info = {}

        # Copy the board so the caller never gets mutated.
        root = board.copy(stack=False)
        best_move: Optional[chess.Move] = None
        best_score = -INF
        best_pv: List[str] = []

        alpha = -INF
        beta = INF

        for depth in range(1, max_depth + 1):
            if self.stop:
                break

            # aspiration window around previous score
            if depth > 1 and best_score > -INF // 2:
                window = 50
                alpha = best_score - window
                beta = best_score + window
            else:
                alpha = -INF
                beta = INF

            while True:
                score = self.negamax(root, depth, alpha, beta, 0)
                if self.stop:
                    break

                # Fail low / fail high with aspiration window
                if score <= alpha and alpha > -INF // 2:
                    alpha -= 100
                    continue
                if score >= beta and beta < INF // 2:
                    beta += 100
                    continue
                best_score = score
                break

            if self.stop:
                break

            tt_entry = self.tt.get(root.fen())
            if tt_entry and tt_entry.best_move is not None:
                best_move = tt_entry.best_move

            elapsed = time.perf_counter() - self.start_time
            nps = int(self.nodes / max(elapsed, 0.001))
            pv = []
            if best_move is not None:
                pv.append(best_move.uci())

            self.last_info = {
                "depth": depth,
                "score": best_score,
                "nodes": self.nodes,
                "nps": nps,
                "time_ms": int(elapsed * 1000),
                "pv": pv,
            }

        self.killers.clear()
        return best_move
