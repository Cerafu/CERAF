"""
engine_core.py
CERAF Core Intelligence: Negamax, Alpha-Beta Pruning, Transposition Tables, and Quiescence Search.
(Adapted for native python-chess integration)
"""
import time
import logging
import chess
from typing import Optional, List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

# Transposition Table Flags
TT_EXACT = 0   # Exact evaluation score
TT_ALPHA = 1   # Upper bound (Failed low)
TT_BETA = 2    # Lower bound (Failed high)

# MVV-LVA (Most Valuable Victim - Least Valuable Aggressor) Weights
PIECE_VALUES = {
    'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 20000,
    'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000,
    None: 0
}

class CERAFEngine:
    __slots__ = [
        'brain', 'transposition_table', 'killer_moves', 'history_heuristic',
        'nodes_evaluated', 'start_time', 'max_time', 'stop_flag'
    ]

    def __init__(self, brain: Any):
        self.brain = brain
        self.transposition_table: Dict[int, Tuple[int, int, int, Any]] = {}
        self.killer_moves: Dict[int, List[Any]] = {} 
        self.history_heuristic: Dict[Tuple[int, int], int] = {}
        
        self.nodes_evaluated: int = 0
        self.start_time: float = 0.0
        self.max_time: float = 0.0
        self.stop_flag: bool = False

    def _check_time(self) -> None:
        if self.nodes_evaluated & 2047 == 0:
            if time.time() - self.start_time > self.max_time:
                self.stop_flag = True

    def evaluate_static(self, board: chess.Board) -> int:
        """Simple material evaluator since python-chess doesn't have one built-in."""
        score = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                val = PIECE_VALUES[piece.symbol()]
                if piece.color == chess.WHITE:
                    score += val
                else:
                    score -= val
        # Return perspective score (positive means good for the side to move)
        return score if board.turn == chess.WHITE else -score

    def score_move(self, board: chess.Board, move: chess.Move, ply: int) -> int:
        """Calculates move priority for sorting to maximize Alpha-Beta pruning."""
        score = 0
        if board.is_capture(move):
            # Target piece (fallback to 100 for En Passant where to_square is empty)
            captured_piece = board.piece_at(move.to_square)
            cap_val = PIECE_VALUES[captured_piece.symbol()] if captured_piece else 100
            
            moving_piece = board.piece_at(move.from_square)
            move_val = PIECE_VALUES[moving_piece.symbol()] if moving_piece else 100
            
            score += 10000 + cap_val - move_val
        elif move.promotion:
            # Add value for Queen promotion
            score += 9000 + 900 
        else:
            # Killer Move Heuristic
            killers = self.killer_moves.get(ply, [])
            if move in killers:
                score += 5000
            # History Heuristic fallback
            score += self.history_heuristic.get((move.from_square, move.to_square), 0)
        return score

    def order_moves(self, board: chess.Board, moves: List[chess.Move], ply: int) -> List[chess.Move]:
        return sorted(moves, key=lambda m: self.score_move(board, m, ply), reverse=True)

    def quiescence_search(self, board: chess.Board, alpha: int, beta: int) -> int:
        self.nodes_evaluated += 1
        self._check_time()
        if self.stop_flag:
            return 0

        # EPD string acts as a perfect board hash without move counters
      # Generate the raw EPD string as a stable, persistent board identifier
        board_epd = board.epd()
        learning_multiplier = self.brain.get_multiplier(board_epd)
        stand_pat = int(self.evaluate_static(board) * learning_multiplier)

        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        # Generate ONLY tactical moves
        tactical_moves = list(board.generate_legal_captures())
        tactical_moves = self.order_moves(board, tactical_moves, ply=0)

        for move in tactical_moves:
            board.push(move)
            score = -self.quiescence_search(board, -beta, -alpha)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.nodes_evaluated += 1
        self._check_time()
        if self.stop_flag:
            return 0

        board_hash = hash(board.epd())
        original_alpha = alpha
        
        if board_hash in self.transposition_table:
            tt_depth, tt_score, tt_flag, _ = self.transposition_table[board_hash]
            if tt_depth >= depth:
                if tt_flag == TT_EXACT:
                    return tt_score
                elif tt_flag == TT_ALPHA and tt_score <= alpha:
                    return alpha
                elif tt_flag == TT_BETA and tt_score >= beta:
                    return beta

        if depth == 0 or board.is_game_over():
            return self.quiescence_search(board, alpha, beta)

        best_score = -float('inf')
        best_move = None
        hash_flag = TT_ALPHA

        moves = list(board.legal_moves)
        if not moves:
            if board.is_check():
                return -30000 + ply  # Checkmate
            return 0  # Stalemate

        moves = self.order_moves(board, moves, ply)

        for move in moves:
            board.push(move)
            score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()

            if self.stop_flag:
                return 0

            if score > best_score:
                best_score = score
                best_move = move

            if score > alpha:
                alpha = score
                hash_flag = TT_EXACT

            if alpha >= beta:
                hash_flag = TT_BETA
                if not board.is_capture(move):
                    self.history_heuristic[(move.from_square, move.to_square)] = self.history_heuristic.get((move.from_square, move.to_square), 0) + (depth * depth)
                    if ply not in self.killer_moves:
                        self.killer_moves[ply] = []
                    if move not in self.killer_moves[ply]:
                        self.killer_moves[ply].insert(0, move)
                        self.killer_moves[ply] = self.killer_moves[ply][:2]
                break

        self.transposition_table[board_hash] = (depth, best_score, hash_flag, best_move)
        return best_score

    def search(self, board: chess.Board, max_time: float = 2.0, max_depth: int = 100) -> Optional[chess.Move]:
        self.start_time = time.time()
        self.max_time = max_time
        self.stop_flag = False
        self.nodes_evaluated = 0
        
        best_move = None
        
        for current_depth in range(1, max_depth + 1):
            if self.stop_flag:
                break
                
            score = self.negamax(board, current_depth, -50000, 50000, ply=0)
            
            if self.stop_flag:
                break
                
            tt_entry = self.transposition_table.get(hash(board.epd()))
            if tt_entry:
                best_move = tt_entry[3]
                
            elapsed = time.time() - self.start_time
            nps = int(self.nodes_evaluated / (elapsed + 0.0001))
            
            logger.info(f"info depth {current_depth} score cp {score} nodes {self.nodes_evaluated} nps {nps} time {int(elapsed * 1000)}")

        self.killer_moves.clear()
        return best_move
