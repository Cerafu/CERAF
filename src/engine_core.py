"""
engine_core.py
CERAF Core Intelligence: Negamax, Alpha-Beta Pruning, Transposition Tables, and Quiescence Search.
"""
import time
import logging
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
        # Killer moves: stores 2 non-capture moves per depth that caused a beta cutoff
        self.killer_moves: Dict[int, List[Any]] = {} 
        # History heuristic: scores quiet moves that are good across different branches
        self.history_heuristic: Dict[Tuple[int, int], int] = {}
        
        self.nodes_evaluated: int = 0
        self.start_time: float = 0.0
        self.max_time: float = 0.0
        self.stop_flag: bool = False

    def _check_time(self) -> None:
        """Polls the clock every 2048 nodes to minimize syscall overhead."""
        if self.nodes_evaluated & 2047 == 0:
            if time.time() - self.start_time > self.max_time:
                self.stop_flag = True

    def score_move(self, move: Any, ply: int) -> int:
        """
        Calculates move priority for sorting. 
        Higher scores are evaluated first, maximizing Alpha-Beta pruning efficiency.
        """
        score = 0
        if move.capture:
            # MVV-LVA: E.g., Pawn taking Queen = 900 - 100 + 10000 = 10800
            score += 10000 + PIECE_VALUES[move.captured_piece] - PIECE_VALUES[move.piece]
        elif move.promotion:
            score += 9000 + PIECE_VALUES[move.promotion]
        else:
            # Killer Move Heuristic
            killers = self.killer_moves.get(ply, [])
            if move in killers:
                score += 5000
            # History Heuristic fallback
            score += self.history_heuristic.get((move.origin, move.target), 0)
        return score

    def order_moves(self, moves: List[Any], ply: int) -> List[Any]:
        """Sorts moves based on heuristic priority."""
        return sorted(moves, key=lambda m: self.score_move(m, ply), reverse=True)

    def quiescence_search(self, board: Any, alpha: int, beta: int) -> int:
        """
        Mitigates the Horizon Effect by continuing the search until the board is 'quiet'
        (no profitable captures exist).
        """
        self.nodes_evaluated += 1
        self._check_time()
        if self.stop_flag:
            return 0

        # Base evaluation integrated with the reinforcement learning ledger
        board_hash = board.zobrist_hash()
        learning_multiplier = self.brain.get_multiplier(str(board_hash))
        stand_pat = int(board.evaluate_static() * learning_multiplier)

        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        # Generate ONLY tactical moves (captures/promotions)
        tactical_moves = board.generate_tactical_moves()
        tactical_moves = self.order_moves(tactical_moves, ply=0)

        for move in tactical_moves:
            board.apply_move(move)
            score = -self.quiescence_search(board, -beta, -alpha)
            board.undo_move()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def negamax(self, board: Any, depth: int, alpha: int, beta: int, ply: int) -> int:
        """
        The core mathematically optimized Alpha-Beta search.
        Relies on the zero-sum property: score_max(a, b) == -score_min(-b, -a).
        """
        self.nodes_evaluated += 1
        self._check_time()
        if self.stop_flag:
            return 0

        # 1. Transposition Table Lookup
        board_hash = board.zobrist_hash()
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

        # 2. Base Case: Drop into Quiescence
        if depth == 0 or board.is_game_over():
            return self.quiescence_search(board, alpha, beta)

        best_score = -float('inf')
        best_move = None
        hash_flag = TT_ALPHA

        # 3. Move Generation and Ordering
        moves = board.generate_legal_moves()
        if not moves:
            if board.is_in_check():
                return -30000 + ply  # Checkmate (prefer faster mates)
            return 0  # Stalemate

        moves = self.order_moves(moves, ply)

        for move in moves:
            board.apply_move(move)
            # Mathematical recursion: flip perspective and bounds
            score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.undo_move()

            if self.stop_flag:
                return 0

            if score > best_score:
                best_score = score
                best_move = move

            if score > alpha:
                alpha = score
                hash_flag = TT_EXACT

            # 4. Alpha-Beta Pruning (Beta Cutoff)
            if alpha >= beta:
                hash_flag = TT_BETA
                # Record Killer and History heuristics for quiet moves
                if not move.capture:
                    self.history_heuristic[(move.origin, move.target)] = self.history_heuristic.get((move.origin, move.target), 0) + (depth * depth)
                    if ply not in self.killer_moves:
                        self.killer_moves[ply] = []
                    if move not in self.killer_moves[ply]:
                        self.killer_moves[ply].insert(0, move)
                        self.killer_moves[ply] = self.killer_moves[ply][:2] # Keep only top 2
                break

        # 5. Transposition Table Store
        self.transposition_table[board_hash] = (depth, best_score, hash_flag, best_move)
        return best_score

    def search(self, board: Any, max_time: float = 2.0, max_depth: int = 100) -> Optional[Any]:
        """
        Iterative Deepening framework. Wraps the Negamax loop to ensure
        CERAF always has a valid move to return before time runs out.
        """
        self.start_time = time.time()
        self.max_time = max_time
        self.stop_flag = False
        self.nodes_evaluated = 0
        
        best_move = None
        
        # Iterative Deepening: Search depth 1, then 2, then 3...
        for current_depth in range(1, max_depth + 1):
            if self.stop_flag:
                break
                
            # Initial Alpha/Beta window
            score = self.negamax(board, current_depth, -50000, 50000, ply=0)
            
            if self.stop_flag:
                break
                
            # Extract the best move path from the Transposition Table
            tt_entry = self.transposition_table.get(board.zobrist_hash())
            if tt_entry:
                best_move = tt_entry[3]
                
            elapsed = time.time() - self.start_time
            nps = int(self.nodes_evaluated / (elapsed + 0.0001))
            
            # Output UCI-compliant info string
            logger.info(f"info depth {current_depth} score cp {score} nodes {self.nodes_evaluated} nps {nps} time {int(elapsed * 1000)}")

        # Clear heuristics between moves to prevent stale data poisoning the tree
        self.killer_moves.clear()
        
        return best_move
