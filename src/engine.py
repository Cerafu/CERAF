"""
Python UCI Chess Engine Prototype with Self-Learning Ledger
Zero external dependencies.
"""
import sys
import json
import os
import random
import time

class Brain:
    """Handles the persistent reinforcement learning ledger."""
    def __init__(self, ledger_path="brain.json"):
        self.ledger_path = ledger_path
        self.knowledge = self._load()

    def _load(self):
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save(self):
        with open(self.ledger_path, 'w') as f:
            json.dump(self.knowledge, f, indent=4)

    def evaluate_position(self, fen):
        """Returns the learned score of a position, defaults to 0.0."""
        return self.knowledge.get(fen, 0.0)

    def learn(self, fen, reward):
        """Updates the position's weight based on game outcome."""
        current_score = self.evaluate_position(fen)
        # Simple learning rate adjustment
        self.knowledge[fen] = round(current_score + (reward * 0.1), 4)
        self.save()


class Engine:
    """Manages the chess board state and search algorithm."""
    def __init__(self, brain):
        self.brain = brain
        self.current_fen = "startpos"
        self.moves = []

    def set_position(self, commands):
        """Parses the UCI position command."""
        if "startpos" in commands:
            self.current_fen = "startpos"
            if "moves" in commands:
                moves_idx = commands.index("moves")
                self.moves = commands[moves_idx + 1:]
            else:
                self.moves = []
        elif "fen" in commands:
            fen_idx = commands.index("fen")
            moves_idx = commands.index("moves") if "moves" in commands else len(commands)
            self.current_fen = " ".join(commands[fen_idx + 1:moves_idx])
            if "moves" in commands:
                self.moves = commands[moves_idx + 1:]
            else:
                self.moves = []

    def calculate_best_move(self):
        """
        Prototype logic: In a full engine, this runs Alpha-Beta pruning over bitboards.
        Here, we generate dummy pseudo-legal moves and pick one based on Brain weights.
        """
        # Dummy move list for prototype demonstration (e2e4, d2d4, g1f3, b1c3)
        candidate_moves = ["e2e4", "d2d4", "g1f3", "b1c3"] 
        
        best_move = random.choice(candidate_moves)
        best_score = -float('inf')

        for move in candidate_moves:
            # Simulate lookahead fen
            simulated_fen = f"{self.current_fen} {move}" 
            score = self.brain.evaluate_position(simulated_fen)
            
            if score > best_score:
                best_score = score
                best_move = move

        return best_move

def uci_loop():
    """The master UCI communication loop."""
    brain = Brain()
    engine = Engine(brain)

    while True:
        try:
            line = sys.stdin.readline().strip()
        except KeyboardInterrupt:
            break

        if not line:
            continue

        tokens = line.split()
        command = tokens[0]

        if command == "uci":
            print("id name PyChess Learning Prototype")
            print("id author You")
            print("uciok")
            sys.stdout.flush()

        elif command == "isready":
            print("readyok")
            sys.stdout.flush()

        elif command == "position":
            engine.set_position(tokens)

        elif command == "go":
            # Simulate thinking time
            time.sleep(0.5)
            best_move = engine.calculate_best_move()
            print(f"bestmove {best_move}")
            sys.stdout.flush()

        elif command == "gameover":
            # Custom command to trigger learning after a match
            # Example: gameover 1.0 (win), gameover -1.0 (loss)
            if len(tokens) > 1:
                reward = float(tokens[1])
                engine.brain.learn(engine.current_fen, reward)

        elif command == "quit":
            break

if __name__ == "__main__":
    uci_loop()
