import streamlit as st
import chess
import chess.pgn
import chess.engine
import chess.svg  # Needed to draw the visual board
import io
import json
import os
import platform
from google import genai

# Calculate the exact, absolute path to the folder containing this app.py file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if platform.system() == "Windows":
    ENGINE_PATH = os.path.join(BASE_DIR, "stockfish.exe")
else:
    ENGINE_PATH = os.path.join(BASE_DIR, "stockfish")

# --- CONFIGURATION ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))

# Initialize the new Gemini Client (Notice there is no genai.configure line here!)
if API_KEY:
    gemini_client = genai.Client(api_key=API_KEY)
else:
    st.error("Gemini API Key missing! Please configure it in your Streamlit Secrets.")
    gemini_client = None

def classify_move(cp_loss, move_index, prev_eval):
    if move_index < 10: return "Book"
    if cp_loss <= 10: return "Best"
    if cp_loss <= 25: return "Excellent"
    if cp_loss <= 50: return "Good"
    if cp_loss <= 100: return "Inaccuracy"
    if cp_loss <= 250: return "Mistake"
    if cp_loss > 250:
        if prev_eval > 200: return "Miss"
        return "Blunder"
    return "Good"

def get_coach_comments(move_data, player_color):
    if not gemini_client:
        return []
        
    # NEW: We pass the standard evaluation bar (e.g., "+1.50", "-0.75", "#2") instead of cp_loss
    prompt_data = [{"move": m["move"], "evaluation": m["evaluation"], "by": m["turn"]} for m in move_data]
    
    prompt = f"""You are an expert chess coach analyzing a game for a student playing {player_color}.
    
    Please evaluate and classify each move using these exact standards:
    - Book: A book move is a move that is well-known to opening theory. 
    - Brilliant: Special moves that find a good, engine-approved piece sacrifice. It is a sharp, critical, or difficult tactical shot.
    - Great: The only good move in a specific position. Anything else throws away your advantage or significantly worsens your standing.
    - Best: The number one choice of the chess engine.
    - Excellent: A very strong move that is nearly as good as the top engine choice, though slightly less optimal.
    - Good: A decent and perfectly playable move that doesn't damage your position.
    - Inaccuracy: A move that makes your position slightly worse or gives up a small advantage.
    - Mistake: A move that noticeably worsens your position or hands your opponent a clear advantage.
    - Miss: A missed opportunity to capitalize on a tactical advantage, such as leaving a hanging piece unpunished.
    - Blunder: A severe tactical error that drastically shifts the game—such as giving away a free piece, walking into a mate, or losing a dominant advantage.

    CRITICAL RULES FOR READING THE EVALUATION:
    - The evaluation is ALWAYS from White's perspective.
    - Positive numbers (+1.50) mean White is winning by that many pawn equivalents.
    - Negative numbers (-2.00) mean Black is winning by that many pawn equivalents.
    - 0.00 means the position is dead equal.
    - # numbers (e.g., #3) mean forced checkmate in that many moves.
    
    HOW TO JUDGE A MOVE:
    To classify a move, look at the CHANGE in the evaluation from the previous move.
    - If White plays and the eval drops from +3.00 to 0.00, White lost 3 pawns of advantage (Mistake/Blunder).
    - If Black plays and the eval goes from -1.00 to +4.00, Black just gave White a 5-pawn advantage (Blunder).
    - If a player is losing heavily (e.g., -6.00) and makes a move that keeps it at -6.00, that is still a "Best" or "Good" move because they didn't make the position any worse!

    Here is the sequential list of moves and the Stockfish Evaluation Bar AFTER each move is played: 
    DATA: {json.dumps(prompt_data)}
    
    For EACH move, strictly apply these criteria to determine the classification label, and provide a one-sentence instructional comment. 
    You MUST return ONLY a valid JSON array of objects. Do not include markdown blocks like ```json.
    Example format:
    [
        {{"classification": "Excellent", "comment": "Developing the knight here controls the center beautifully."}},
        {{"classification": "Blunder", "comment": "This allows White to fork your king and rook, flipping the evaluation."}}
    ]"""
    
    try:
        response = gemini_client.models.generate_content(
            model='models/gemini-2.5-flash',
            contents=prompt
        )
        clean_text = response.text.strip().strip('`').replace('json\n', '')
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"Coach API Error: {str(e)}")
        return []

# A simple placeholder so the code doesn't crash before the AI finishes its work
def classify_move_fallback(cp_loss, move_index):
    return "Analyzing..."

def analyze_game(pgn_str, engine_path, player_color):
    try:
        if platform.system() != "Windows" and os.path.exists(engine_path):
            os.chmod(engine_path, 0o755)
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except Exception as e:
        st.error(f"Failed to start Stockfish engine.\n\nI looked exactly here: `{engine_path}`\n\nError: {e}")
        return None, 0

    pgn_io = io.StringIO(pgn_str)
    game = chess.pgn.read_game(pgn_io)
    if game is None:
        st.error("Invalid PGN format.")
        return None, 0
    
    board = game.board()
    move_data = []
    total_cp_loss = 0
    analyzed_moves = 0
    
    # NEW: Configure Engine Limit to Depth 14
    limit = chess.engine.Limit(depth=14)
    
    prev_info = engine.analyse(board, limit)
    prev_cp_white = prev_info["score"].white().score(mate_score=10000)
    
    for i, move in enumerate(game.mainline_moves()):
        san_move = board.san(move)
        board.push(move)
        
        info = engine.analyse(board, limit)
        
        # 1. GET THE RAW SCORE FROM WHITE'S PERSPECTIVE
        score = info["score"].white()
        curr_cp_white = score.score(mate_score=10000)
        
        # 2. FORMAT IT LIKE A REAL EVALUATION BAR (e.g., "+1.50" or "#3")
        if score.is_mate():
            eval_str = f"#{score.mate()}"
        else:
            # Divide centipawns by 100 to get standard pawn units
            eval_str = f"{score.score() / 100.0:+.2f}"
        
        # Calculate cp_loss for our math fallback and total calculation
        if board.turn == chess.BLACK:
            cp_loss = prev_cp_white - curr_cp_white
            is_player_move = (player_color == "White")
            turn_name = "White"
        else:
            cp_loss = curr_cp_white - prev_cp_white
            is_player_move = (player_color == "Black")
            turn_name = "Black"
            
        cp_loss = max(0, cp_loss) 
        if is_player_move:
            total_cp_loss += cp_loss
            analyzed_moves += 1
            
        move_data.append({
            "move_number": (i // 2) + 1,
            "turn": turn_name,
            "move": san_move, 
            "uci_move": move.uci(), 
            "cp_loss": cp_loss,  
            "evaluation": eval_str, # NEW: Save the formatted evaluation bar
            "classification": classify_move_fallback(cp_loss, i), 
            "fen": board.fen()      
        })
        prev_cp_white = curr_cp_white

    engine.quit()
    acpl = total_cp_loss / max(1, analyzed_moves)
    estimated_rating = round(3100/(2.718**(0.01*acpl)))
    # acpl = total_cp_loss / max(1, analyzed_moves)
    # return move_data, estimated_rating, round(acpl, 1) # Return the ACPL
    # acpl = total_cp_loss / max(1, analyzed_moves)
    print(f"DEBUG: Calculated ACPL is {acpl}") # This prints to your terminal
    return move_data, estimated_rating, round(acpl, 1)

# --- UI DISPLAY ---
st.set_page_config(page_title="AI Chess Reviewer", layout="wide")
st.title("♟️ AI Chess Game Reviewer")

# NEW: Initialize Session State Memory
if "analysis_complete" not in st.session_state:
    st.session_state.analysis_complete = False

player_color = st.radio("Your Color:", ("White", "Black"), horizontal=True)
pgn_input = st.text_area("Paste PGN here:", height=150)

if st.button("Review Game", type="primary"):
    if not pgn_input:
        st.warning("Please paste a game PGN first.")
    else:
        with st.spinner("Stockfish running deep analysis (Depth 12)..."):
            moves, rating, acpl = analyze_game(pgn_input, ENGINE_PATH, player_color)
            
        if moves:
            with st.spinner("AI Coach is drafting your review..."):
                ai_responses = get_coach_comments(moves, player_color)
            
            # --- FIX: Split the classification and the comment ---
            final_comments = []
            for i, move in enumerate(moves):
                if i < len(ai_responses) and isinstance(ai_responses[i], dict):
                    # 1. Update the classification in the move object
                    move["classification"] = ai_responses[i].get("classification", "Good")
                    # 2. Extract ONLY the comment string
                    final_comments.append(ai_responses[i].get("comment", "No comment provided."))
                else:
                    final_comments.append("Coach is thinking...")
            
            # Save the clean list of strings, not the dictionaries
            st.session_state.moves = moves
            st.session_state.comments = final_comments 
            st.session_state.rating = rating
            st.session_state.analysis_complete = True

# if st.button("Review Game", type="primary"):
#     if not pgn_input:
#         st.warning("Please paste a game PGN first.")
#     else:
#         with st.spinner("Stockfish running deep analysis..."):
#             # 1. Run Stockfish
#             moves, rating, acpl = analyze_game(pgn_input, ENGINE_PATH, player_color)
            
#         # 2. Store results in Session State
#         st.session_state.rating = rating
#         st.session_state.acpl = acpl
#         st.session_state.moves = moves
        
#         # 3. Skip the AI Coach entirely
#         # We just create empty placeholders so the UI doesn't look for comments
#         st.session_state.comments = ["No coach feedback requested." for _ in moves]
        
#         # 4. Mark complete
#         st.session_state.analysis_complete = True
#         st.success("Analysis complete! (Coach disabled)")

# --- INTERACTIVE CHESS BOARD ---
if st.session_state.analysis_complete:
    st.divider()
    
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric(label="Estimated Performance Rating", value=f"{st.session_state.rating} ELO")
        
    with m_col2:
        # Check if acpl exists in session_state before displaying
        if "acpl" in st.session_state:
            st.metric(label="Avg. Centipawn Loss (ACPL)", value=f"{st.session_state.acpl}")
    
    st.divider()

    moves = st.session_state.moves
    comments = st.session_state.comments

    # --- 1. MOVE CLASSIFICATION REPORT ---
    st.subheader("📊 Match Accuracy Report")
    
    # Define categories and their display colors
    cat_colors = {
        "Brilliant": "green", "Great": "green", "Best": "green", 
        "Excellent": "green", "Good": "green", "Book": "green", 
        "Inaccuracy": "blue", "Mistake": "orange", "Miss": "red", "Blunder": "red"
    }
    
    # Initialize counting dictionaries
    white_counts = {cat: 0 for cat in cat_colors}
    black_counts = {cat: 0 for cat in cat_colors}
    
    # Tally up moves
    for m in moves:
        cat = m.get("classification", "Good")
        if m["turn"] == "White":
            if cat in white_counts: white_counts[cat] += 1
        else:
            if cat in black_counts: black_counts[cat] += 1

    # Display the report with a clean table-like layout
    rep_col1, rep_col2 = st.columns(2)
    
    for col, data in [(rep_col1, white_counts), (rep_col2, black_counts)]:
        with col:
            st.markdown(f"### {'⚪ White' if col == rep_col1 else '⚫ Black'}")
            for cat, count in data.items():
                if count > 0:
                    color = cat_colors.get(cat, "gray")
                    # Use a clean icon + bold text format
                    st.markdown(f"- :{color}[**{cat}**]: {count}")
    
    st.divider()

    # --- 2. INTERACTIVE BOARD WITH NAVIGATION ---
    
    # Initialize the button state memory
    if "move_index" not in st.session_state:
        st.session_state.move_index = 1

    # Callback functions to handle button clicks safely
    def go_previous():
        if st.session_state.move_index > 1:
            st.session_state.move_index -= 1

    def go_next():
        if st.session_state.move_index < len(moves):
            st.session_state.move_index += 1

    # Draw the Navigation Buttons
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    
    with nav_col1:
        st.button("⬅️ Previous", on_click=go_previous, disabled=(st.session_state.move_index <= 1), use_container_width=True)
        
    with nav_col2:
        st.markdown(f"<h4 style='text-align: center; margin-top: 0px;'>Move {st.session_state.move_index} of {len(moves)}</h4>", unsafe_allow_html=True)
        
    with nav_col3:
        st.button("Next ➡️", on_click=go_next, disabled=(st.session_state.move_index >= len(moves)), use_container_width=True)

    # Grab the data for the currently selected move
    current_move = moves[st.session_state.move_index - 1]
    
    # Side-by-Side Layout for Board and Comments
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        # Draw the board and highlight the last piece moved
        move_obj = chess.Move.from_uci(current_move["uci_move"])
        board_svg = chess.svg.board(board=chess.Board(current_move["fen"]), lastmove=move_obj, size=400)
        st.markdown(board_svg, unsafe_allow_html=True)
        
    with col2:
        st.subheader(f"{current_move['turn']} played:")
        
        # Determine Color
        cat = current_move["classification"]
        if cat in ["Blunder", "Miss"]: color = "🔴"
        elif cat in ["Brilliant", "Great", "Best", "Excellent", "Book"]: color = "🟢"
        elif cat in ["Mistake"]: color = "🟠"
        else: color = "🔵"
        
        # Make the Classification label HUGE and color-coded
        st.markdown(f"# {color} {cat}")
        
        # Keep the move notation and comment separate
        st.markdown(f"### Move: **{current_move['move']}**")
        
        if (st.session_state.move_index - 1) < len(comments):
            st.info(f"**Coach's Tactical Insight:**\n\n{comments[st.session_state.move_index - 1]}")

    st.divider()
    
    # Optional: Keep the old list available in a dropdown if they still want to scan it quickly
    with st.expander("Show Full Move List"):
        for i, m in enumerate(moves):
            color_tag = "⚪" if m["turn"] == "White" else "⚫"
            status_color = "normal"
            if m["classification"] in ["Blunder", "Miss"]: status_color = "red"
            elif m["classification"] in ["Brilliant", "Great", "Best", "Excellent", "Book"]: status_color = "green"
            elif m["classification"] == "Mistake": status_color = "orange"
            
            # Highlight the current move in the list
            bold_prefix = "**👉** " if (i + 1) == st.session_state.move_index else ""
            st.markdown(f"{bold_prefix}**{m['move_number']}. {color_tag} {m['move']}** — :{status_color}[**{m['classification']}**]")