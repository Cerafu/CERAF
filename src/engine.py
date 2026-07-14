<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CERAF - Self-Learning AI</title>
    <!-- Load Pyodide for Python execution and Chess.js for client-side move validation -->
    <script src="https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
    
    <style>
        body {
            background-color: #1c1c1c; /* Matches your Tkinter background[cite: 1] */
            color: white;
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            padding: 20px;
            user-select: none;
        }

        #game-container { display: flex; gap: 20px; }

        /* Board Container with relative positioning for SVG Arrows */
        #board-wrapper {
            position: relative;
            width: 576px; /* 8 squares * 72px[cite: 1] */
            height: 576px;
        }

        #board {
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            grid-template-rows: repeat(8, 1fr);
            width: 100%;
            height: 100%;
            border: 2px solid #333;
        }

        .square {
            width: 72px;
            height: 72px;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 50px;
            cursor: pointer;
            position: relative;
        }

        .light { background-color: #eeeed2; } /* Matches prototype colors[cite: 1] */
        .dark { background-color: #769656; }
        .highlight { background-color: #f7f785 !important; }
        .last-move-light { background-color: #e2e485; }
        .last-move-dark { background-color: #b7c45d; }

        /* Contrasting Pieces: Black outline on White pieces, White outline on Black pieces */
        .piece {
            z-index: 10;
            transition: transform 0.1s;
        }
        .piece.white {
            color: #ffffff; /*[cite: 1] */
            -webkit-text-stroke: 1.5px #1a1a1a;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        .piece.black {
            color: #1a1a1a; /*[cite: 1] */
            -webkit-text-stroke: 1px #ffffff;
            text-shadow: 0 2px 4px rgba(255,255,255,0.3);
        }
        .piece.dragging {
            position: fixed;
            pointer-events: none;
            z-index: 1000;
            transform: scale(1.2);
        }

        /* SVG Overlay for Arrows */
        #arrow-svg {
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            pointer-events: none; /* Lets clicks pass through to the board */
            z-index: 20;
        }
        .arrow-line { stroke: rgba(255, 170, 0, 0.8); stroke-width: 12; stroke-linecap: round; }
        .arrow-head { fill: rgba(255, 170, 0, 0.8); }

        /* Sidebar UI matching your Tkinter layout[cite: 1] */
        #sidebar {
            width: 260px;
            background-color: #262626;
            padding: 10px;
            border-radius: 5px;
            display: flex;
            flex-direction: column;
        }
        #dialogue-frame {
            background-color: #1a1a1a;
            border: 2px solid #4dd0e1;
            padding: 10px;
            margin-bottom: 15px;
        }
        #ceraf-title { color: #4dd0e1; font-weight: bold; font-size: 14px; margin-bottom: 5px; }
        #ceraf-text { font-style: italic; font-size: 14px; color: white; min-height: 40px; }
        
        #log-container { flex-grow: 1; background-color: #121212; padding: 10px; overflow-y: auto; color: #00E676; font-family: monospace; margin-bottom: 15px;}
        #status-label { font-weight: bold; color: #00E676; text-align: center; margin-bottom: 15px; font-size: 16px;}
        button { background-color: #d9534f; color: white; border: none; padding: 10px; font-weight: bold; cursor: pointer; }
        button:hover { background-color: #c9302c; }
    </style>
</head>
<body>

<div id="game-container">
    <div id="board-wrapper">
        <div id="board"></div>
        <svg id="arrow-svg">
            <defs>
                <marker id="arrowhead" markerWidth="4" markerHeight="4" refX="2" refY="2" orient="auto">
                    <polygon points="0 0, 4 2, 0 4" class="arrow-head" />
                </marker>
            </defs>
            <g id="arrows-group"></g>
            <line id="drawing-arrow" class="arrow-line" marker-end="url(#arrowhead)" style="display:none;" />
        </svg>
    </div>

    <div id="sidebar">
        <div id="dialogue-frame">
            <div id="ceraf-title">🧠 CERAF says:</div>
            <div id="ceraf-text">"Loading Pyodide brain modules... Please wait."</div>
        </div>
        <div style="text-align: center; color: #aaa; font-weight: bold; margin-bottom: 5px;">Live Notation Log</div>
        <div id="log-container"></div>
        <div id="status-label">Engine Initializing...</div>
        <button onclick="resetGame()">Restart Match</button>
    </div>
</div>

<script>
    const unicodePieces = {
        'R': '♜', 'N': '♞', 'B': '♝', 'Q': '♛', 'K': '♚', 'P': '♟',
        'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚', 'p': '♟'
    }; // Matching your Tkinter Unicode mapping[cite: 1]

    let game = new Chess();
    const boardEl = document.getElementById("board");
    const arrowsGroup = document.getElementById("arrows-group");
    const drawingArrow = document.getElementById("drawing-arrow");
    const cerafText = document.getElementById("ceraf-text");
    const statusLabel = document.getElementById("status-label");
    const logContainer = document.getElementById("log-container");

    let pyodideReady = false;
    let selectedSquare = null;
    let isDragging = false;
    let dragPieceEl = null;
    let rightClickStartSq = null;

    // --- BOARD RENDERING ---
    function renderBoard() {
        boardEl.innerHTML = "";
        const board = game.board();
        
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const squareName = String.fromCharCode(97 + c) + (8 - r);
                const sqEl = document.createElement("div");
                sqEl.classList.add("square", (r + c) % 2 === 0 ? "light" : "dark");
                sqEl.dataset.sq = squareName;

                if (selectedSquare === squareName) sqEl.classList.add("highlight");

                const piece = board[r][c];
                if (piece) {
                    const pieceEl = document.createElement("div");
                    pieceEl.classList.add("piece", piece.color === 'w' ? "white" : "black");
                    pieceEl.innerText = unicodePieces[piece.color === 'w' ? piece.type.toUpperCase() : piece.type];
                    sqEl.appendChild(pieceEl);
                }

                // Event Listeners for Click, Drag, and Arrows
                sqEl.addEventListener("mousedown", handleMouseDown);
                sqEl.addEventListener("mouseup", handleMouseUp);
                sqEl.addEventListener("contextmenu", (e) => e.preventDefault());
                
                boardEl.appendChild(sqEl);
            }
        }
    }

    // --- DRAG, DROP, CLICK & ARROWS LOGIC ---
    function handleMouseDown(e) {
        if (!pyodideReady || game.game_over()) return;
        
        const targetSq = e.currentTarget.dataset.sq;

        // Right Click: Start drawing arrow
        if (e.button === 2) {
            rightClickStartSq = targetSq;
            const rect = e.currentTarget.getBoundingClientRect();
            const boardRect = boardEl.getBoundingClientRect();
            const startX = rect.left - boardRect.left + 36;
            const startY = rect.top - boardRect.top + 36;
            
            drawingArrow.setAttribute("x1", startX);
            drawingArrow.setAttribute("y1", startY);
            drawingArrow.setAttribute("x2", startX);
            drawingArrow.setAttribute("y2", startY);
            drawingArrow.style.display = "block";
            return;
        }

        // Left Click: Clear arrows
        arrowsGroup.innerHTML = ""; 

        // Handle Click-to-Move or Start Drag
        if (selectedSquare) {
            const moveResult = attemptMove(selectedSquare, targetSq);
            if (moveResult) {
                selectedSquare = null;
                return;
            }
        }

        const piece = game.get(targetSq);
        if (piece && piece.color === 'w') {
            selectedSquare = targetSq;
            isDragging = true;
            
            // Create drag phantom
            dragPieceEl = e.currentTarget.querySelector('.piece').cloneNode(true);
            dragPieceEl.classList.add('dragging');
            document.body.appendChild(dragPieceEl);
            movePhantom(e);
            renderBoard(); // Re-render to highlight selected
        } else {
            selectedSquare = null;
            renderBoard();
        }
    }

    document.addEventListener("mousemove", (e) => {
        if (isDragging && dragPieceEl) movePhantom(e);
        
        // Update arrow drawing
        if (rightClickStartSq) {
            const boardRect = boardEl.getBoundingClientRect();
            drawingArrow.setAttribute("x2", e.clientX - boardRect.left);
            drawingArrow.setAttribute("y2", e.clientY - boardRect.top);
        }
    });

    function handleMouseUp(e) {
        // Right Click Release: Finalize arrow
        if (e.button === 2 && rightClickStartSq) {
            const endSq = e.currentTarget.dataset.sq;
            if (endSq && endSq !== rightClickStartSq) {
                const newArrow = drawingArrow.cloneNode(true);
                arrowsGroup.appendChild(newArrow);
            }
            drawingArrow.style.display = "none";
            rightClickStartSq = null;
            return;
        }

        // Left Click Release (Drop)
        if (isDragging) {
            isDragging = false;
            if (dragPieceEl) { document.body.removeChild(dragPieceEl); dragPieceEl = null; }
            
            const elements = document.elementsFromPoint(e.clientX, e.clientY);
            const targetEl = elements.find(el => el.classList.contains('square'));
            
            if (targetEl && targetEl.dataset.sq !== selectedSquare) {
                attemptMove(selectedSquare, targetEl.dataset.sq);
                selectedSquare = null;
            }
            renderBoard();
        }
    }

    function movePhantom(e) {
        dragPieceEl.style.left = `${e.clientX - 36}px`;
        dragPieceEl.style.top = `${e.clientY - 36}px`;
    }

    function attemptMove(from, to) {
        // Handle Auto-Queen promotion
        const move = { from: from, to: to, promotion: 'q' };
        const result = game.move(move);
        
        if (result) {
            logMove(result.san, true);
            cerafText.innerText = '"Hmm, let\'s try this."'; // CERAF Dialogue[cite: 1]
            renderBoard();
            
            if (!checkGameOver()) {
                statusLabel.innerText = "CERAF is calculating...";
                statusLabel.style.color = "#FFC107";
                setTimeout(triggerPythonAI, 50);
            }
            return true;
        }
        return false;
    }

    function logMove(san, isWhite) {
        const p = document.createElement("div");
        p.innerText = isWhite ? `${Math.ceil(game.history().length/2)}. ${san}` : `   ... ${san}`;
        logContainer.appendChild(p);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    function checkGameOver() {
        if (game.game_over()) {
            if (game.in_checkmate()) {
                statusLabel.innerText = game.turn() === 'w' ? "CERAF WINS" : "YOU WIN";
                statusLabel.style.color = game.turn() === 'w' ? "#ef5350" : "#00E676";
                cerafText.innerText = game.turn() === 'w' ? '"Checkmate! hehehe."' : '"I yield! You are truly a master."'; //[cite: 1]
            } else {
                statusLabel.innerText = "DRAW";
                statusLabel.style.color = "#aaaaaa";
            }
            return true;
        }
        return false;
    }

    function resetGame() {
        game.reset();
        selectedSquare = null;
        arrowsGroup.innerHTML = "";
        logContainer.innerHTML = "";
        statusLabel.innerText = "Your Turn (White)";
        statusLabel.style.color = "#00E676";
        cerafText.innerText = '"CERAF online! Let\'s play a beautiful game."'; //[cite: 1]
        renderBoard();
    }

// --- PYODIDE (PYTHON BACKEND) INTEGRATION ---
    async function initPyodide() {
        cerafText.innerText = '"Waking up... Loading Python environment..."';
        
        window.pyodide = await loadPyodide();
        await pyodide.loadPackage("micropip");
        const micropip = pyodide.pyimport("micropip");
        await micropip.install("chess"); 

        cerafText.innerText = '"Fetching engine.py from source..."';

        try {
            // 1. Fetch your actual engine code from the src/ directory
            const response = await fetch('src/engine.py');
            if (!response.ok) throw new Error("Could not find src/engine.py");
            const engineCode = await response.text();

            // 2. Write the file into Pyodide's virtual file system
            pyodide.FS.writeFile('/home/pyodide/engine.py', engineCode);

            // 3. Set up the Python Bridge to run your specific engine
            await pyodide.runPythonAsync(`
                import sys
                import chess
                sys.path.append('/home/pyodide')
                
                # Import the real engine you wrote!
                from engine import CERAFEngine
                
                # Create a simple mock brain for the web version 
                # (since saving JSON files directly to the user's hard drive isn't possible in a browser)
                class WebBrain:
                    def get_multiplier(self, board_hash):
                        return 1.0

                ceraf_brain = WebBrain()
                
                # Initialize your powerful championship-grade engine
                engine = CERAFEngine(brain=ceraf_brain)

                def get_best_move(fen_string):
                    board = chess.Board(fen_string)
                    
                    # Run your actual search algorithm (capped at 1.5 seconds so the browser doesn't freeze)
                    # NOTE: If your engine_core.py expects custom board methods, 
                    # you may need to wrap python-chess here.
                    best_move = engine.search(board, max_time=1.5, max_depth=10)
                    
                    if best_move:
                        # Ensure the move is returned as a UCI string (e.g., 'e2e4') for the Javascript frontend
                        return best_move.uci() if hasattr(best_move, 'uci') else str(best_move)
                    return None
            `);
            
            pyodideReady = true;
            resetGame();
            
        } catch (error) {
            console.error("Engine Load Error:", error);
            cerafText.innerText = '"Error loading engine_core.py! Check the console."';
            statusLabel.innerText = "Engine Failed to Load";
            statusLabel.style.color = "#ef5350";
        }
    }

    async function triggerPythonAI() {
        const fen = game.fen();
        // Call the Python logic
        const bestMoveUCI = await pyodide.runPythonAsync(`get_best_move("${fen}")`);
        
        if (bestMoveUCI) {
            const result = game.move(bestMoveUCI, {sloppy: true});
            logMove(result.san, false);
            cerafText.innerText = '"Your turn! hehehe."'; //[cite: 1]
            statusLabel.innerText = "Your Turn (White)";
            statusLabel.style.color = "#00E676";
            renderBoard();
            checkGameOver();
        }
    }

    // Start App
    renderBoard();
    initPyodide();
</script>
</body>
</html>
