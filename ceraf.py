#!/usr/bin/env python3
import argparse
import logging
import sys
from src.engine_core import uci_loop
from src.selfplay import run_selfplay
from src.tuning import run_tuning
from src.storage import setup_directories

# ceraf.py

def setup_logging():
    """Configures basic logging for the engine."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

if __name__ == "__main__":
    # Initialize the unused logging module
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Ensure all D:\Chess\ directories exist before doing anything
        setup_directories()
        logger.info("Storage directories checked and ready.")

        parser = argparse.ArgumentParser(description="CERAF Self-Learning Chess Engine")
        parser.add_argument('--mode', choices=['uci', 'selfplay', 'tune'], default='uci', 
                            help="Mode to run the engine in.")
        parser.add_argument('--games', type=int, default=10, 
                            help="Number of games for self-play.")
        parser.add_argument('--depth', type=int, default=4, 
                            help="Search depth for self-play.")
        
        args = parser.parse_args()

        if args.mode == 'uci':
            logger.info("Starting UCI loop...")
            uci_loop()
        elif args.mode == 'selfplay':
            logger.info(f"Starting self-play: {args.games} games at depth {args.depth}...")
            run_selfplay(games=args.games, depth=args.depth)
        elif args.mode == 'tune':
            logger.info("Starting evaluation tuning process...")
            run_tuning()
            
    except KeyboardInterrupt:
        logger.info("Process interrupted by user (Ctrl+C). Exiting cleanly.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)
