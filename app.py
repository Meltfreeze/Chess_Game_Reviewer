import streamlit as st
import chess
import chess.pgn
import chess.engine
import chess.svg
import io
import json
import os
import platform
import base64
import math
from google import genai

VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,  # never the "profitable" piece — only ever spent last
}

# --- HELPER FUNCTIONS ---
def get_icon_html(classification):
    icon_path = f"icons/{classification}.png"
    if os.path.exists(icon_path):
        with open(icon_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            return f'<img src="data:image/png;base64,{encoded_string}" width="24" style="vertical-align: middle; margin-right: 8px;">'
    return ""

def format_clock(seconds):
    if seconds is None:
        return "--:--"
    m, s = divmod(int(max(0, seconds)), 60)
    return f"{m}:{s:02d}"

# --- NEW: WIN PROBABILITY CLASSIFIER ---
def cp_to_wp(cp):
    # Cap the CP to prevent math overflow errors on massive mate scores
    cp = max(-10000, min(10000, cp))
    # Standard Elo-style sigmoid curve to calculate Win Probability (0.0 to 1.0)
    return 1 / (1 + 10 ** (-cp / 400))

def _least_valuable_attacker(board, square, color):
    """
    Square of the cheapest `color` piece that can legally recapture on `square`,
    or None if there isn't one.
    """
    attackers = board.attackers(color, square)
    if not attackers:
        return None

    for sq in sorted(attackers, key=lambda s: VALUES.get(board.piece_at(s).piece_type, 0)):
        if board.piece_at(sq).piece_type == chess.KING:
            # the king can't recapture into a square the opponent still covers —
            # that would just be moving into check
            if board.attackers(not color, square):
                continue
        return sq
    return None

def static_exchange_eval(board, move):
    """
    Plays out the entire forced capture sequence on move.to_square — cheapest
    attacker recaptures each time — then unwinds it so each side only "takes"
    when doing so doesn't lose them more than walking away would.

    Returns the net material swing for the side making `move`.
    Negative      -> the mover ends up worse off overall: a genuine sacrifice.
    Zero/positive -> the mover is fine, even if several pieces get traded on the square.
    """
    to_sq, from_sq = move.to_square, move.from_square

    mover = board.piece_at(from_sq)
    if mover is None:
        return 0

    scratch = board.copy(stack=False)  # never touch the real board/move stack

    captured = scratch.piece_at(to_sq)
    gain = [VALUES.get(captured.piece_type, 0) if captured else 0]

    attacker_value = VALUES.get(mover.piece_type, 0)
    side = not mover.color  # opponent gets first crack at recapturing

    scratch.remove_piece_at(from_sq)
    scratch.set_piece_at(to_sq, chess.Piece(mover.piece_type, mover.color))

    depth = 0
    while True:
        attacker_sq = _least_valuable_attacker(scratch, to_sq, side)
        if attacker_sq is None:
            break

        depth += 1
        gain.append(attacker_value - gain[depth - 1])

        attacker_piece = scratch.piece_at(attacker_sq)
        attacker_value = VALUES.get(attacker_piece.piece_type, 0)

        scratch.remove_piece_at(attacker_sq)
        scratch.set_piece_at(to_sq, chess.Piece(attacker_piece.piece_type, attacker_piece.color))
        side = not side

    # negamax unwind: each side only continues the trade if it's not a losing line for them
    while depth:
        gain[depth - 1] = -max(-gain[depth - 1], gain[depth])
        depth -= 1

    return gain[0]

def is_sacrifice(board, move):
    """True if the full exchange on move.to_square leaves the mover down material."""
    if not board.piece_at(move.from_square):
        return False

    # fast path: nothing even attacks the destination, so it can't be a sac
    if not board.attackers(not board.turn, move.to_square):
        return False

    return static_exchange_eval(board, move) < 0

def classify_move(move_number, prev_cp, curr_cp, is_only_move, is_sac):
    wp_before = cp_to_wp(prev_cp)
    wp_after = cp_to_wp(curr_cp)
    wp_loss = wp_before - wp_after
    
    # --- BAD MOVES ---
    if wp_loss >= 0.25:
        return "Blunder"
    elif wp_loss >= 0.17:
        return "Mistake"
    elif wp_loss >= 0.10:
        return "Inaccuracy"
    elif wp_loss >= 0.05:
        return "Good"
    elif wp_loss >= 0.01:
        return "Excellent"
        
    # --- GOOD/SPECIAL MOVES ---
    else:
        # To be brilliant or great, the move must be fundamentally sound (Best)
        
        # BRILLIANT: It's a sacrifice, and Win Probability did NOT decrease significantly
        if is_sac and wp_loss <= 0.01 and wp_after > 0.20:
            return "Brilliant"
            
        # GREAT: It was the only move that didn't ruin the position
        elif is_only_move and wp_after > 0.10:
            return "Great"
            
        else:
            return "Best"

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if platform.system() == "Windows":
    ENGINE_PATH = os.path.join(BASE_DIR, "stockfishw.exe")
else:
    ENGINE_PATH = os.path.join(BASE_DIR, "stockfish")

API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))

if API_KEY:
    gemini_client = genai.Client(api_key=API_KEY)
else:
    st.error("Gemini API Key missing! Please configure it in your Streamlit Secrets.")
    gemini_client = None

# --- AI COACH GENERATION ---
def get_coach_comments(move_data, player_color):
    # Ultra-compressed payload: We only send the move, the eval, and Stockfish's classification
    prompt_data = [{"m": m["move"], "eval": m["evaluation"], "class": m["classification"]} for m in move_data]
    
    prompt = f"""Role: Expert chess coach for {player_color}.
    Task: Write a 1-2 line game summary, and write exactly ONE short sentence of commentary for each move.
    
    The moves have ALREADY been classified by the engine (e.g., Blunder, Best, Inaccuracy). 
    Your job is ONLY to provide the natural language comment explaining the move based on its classification and evaluation.

    CRITICAL: I provided {len(prompt_data)} moves. You MUST return EXACTLY {len(prompt_data)} JSON objects in the "moves" array.
    
    DATA: {json.dumps(prompt_data)}
    
    Format:
    {{
        "game_summary": "...",
        "moves": [
            {{"comment": "<Your 1 sentence explanation>"}}
        ]
    }}"""
    
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction="You are a helpful AI chess coach that outputs strict JSON.",
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        
        clean_text = response.text.strip()
        parsed = json.loads(clean_text)
        
        return parsed.get("game_summary", "A tough game!"), parsed.get("moves", [])
        
    except Exception as e:
        st.error(f"Coach API Error: {str(e)}")
        return "The Coach experienced an error while generating the summary.", []

# --- ANALYSIS ENGINE ---
def analyze_game(pgn_str, engine_path, player_color):
    try:
        if platform.system() != "Windows" and os.path.exists(engine_path):
            os.chmod(engine_path, 0o755)
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except Exception as e:
        st.error(f"Failed to start Stockfish engine.\n\nError: {e}")
        return None, 0, 0, {}

    pgn_io = io.StringIO(pgn_str)
    game = chess.pgn.read_game(pgn_io)
    if game is None:
        st.error("Invalid PGN format.")
        return None, 0, 0, {}
    
    metadata = {
        "White": f"{game.headers.get('White', 'White')} ({game.headers.get('WhiteElo', '?')})",
        "Black": f"{game.headers.get('Black', 'Black')} ({game.headers.get('BlackElo', '?')})"
    }
    
    board = game.board()
    move_data = []
    total_cp_loss = 0
    analyzed_moves = 0
    
    limit = chess.engine.Limit(depth=14)
    # --- NEW: Run Multi-PV right from the start ---
    prev_info = engine.analyse(board, limit, multipv=2)
    prev_cp_white = prev_info[0]["score"].white().score(mate_score=10000)
    
    node = game
    w_clk = None
    b_clk = None
    
    for i, move in enumerate(game.mainline_moves()):
        san_move = board.san(move)
        
        # --- NEW: Check for sacrifice BEFORE the move is made ---
        is_sac = is_sacrifice(board, move)
        
        # --- NEW: Check the second best move of the PREVIOUS position ---
        # This accurately tells us if the move they were about to make was the "Only Move"
        if len(prev_info) > 1:
            prev_second_best_cp_white = prev_info[1]["score"].white().score(mate_score=10000)
        else:
            prev_second_best_cp_white = prev_cp_white
            
        board.push(move)
        
        node = node.variation(move)
        clock_seconds = node.clock()
        if board.turn == chess.BLACK: # White just moved
            w_clk = clock_seconds
        else:
            b_clk = clock_seconds
            
        # --- NEW: Evaluate the new position with Multi-PV ---
        info = engine.analyse(board, limit, multipv=2)
        score = info[0]["score"].white()
        curr_cp_white = score.score(mate_score=10000)
        
        if score.is_mate(): eval_str = f"#{score.mate()}"
        else: eval_str = f"{score.score() / 100.0:+.2f}"
        
        # --- NEW: Get the CP from the moving player's perspective ---
        if board.turn == chess.BLACK: # White just moved
            player_prev_cp = prev_cp_white
            player_curr_cp = curr_cp_white
            second_best_cp = prev_second_best_cp_white
            is_player_move = (player_color == "White")
            turn_name = "White"
        else: # Black just moved
            player_prev_cp = -prev_cp_white
            player_curr_cp = -curr_cp_white
            second_best_cp = -prev_second_best_cp_white
            is_player_move = (player_color == "Black")
            turn_name = "Black"
            
        # --- NEW: Only Move Logic ---
        # Calculate win probability of the best move vs the second best move
        wp_best = cp_to_wp(player_prev_cp)
        wp_second = cp_to_wp(second_best_cp)
        # If the gap between the best move and second best move is huge (20%+), it's an only move!
        is_only_move = (wp_best - wp_second >= 0.20)
            
        # Standard cp_loss for the overall ACPL math
        cp_loss = max(0, player_prev_cp - player_curr_cp) 
        if is_player_move:
            total_cp_loss += cp_loss
            analyzed_moves += 1
            
        # --- NEW: Call the Win Probability classifier! ---
        move_classification = classify_move((i // 2) + 1, player_prev_cp, player_curr_cp, is_only_move, is_sac)
            
        move_data.append({
            "move_number": (i // 2) + 1,
            "turn": turn_name,
            "move": san_move, 
            "uci_move": move.uci(), 
            "cp_loss": cp_loss,  
            "evaluation": eval_str, 
            "classification": move_classification,
            "fen": board.fen(),
            "w_clk": w_clk,
            "b_clk": b_clk
        })
        
        # --- NEW: Save current state for the next iteration ---
        prev_info = info
        prev_cp_white = curr_cp_white

    engine.quit()
    acpl = total_cp_loss / max(1, analyzed_moves)
    estimated_rating = round(3100/(2.718**(0.01*acpl)))
    
    return move_data, estimated_rating, round(acpl, 1), metadata


# --- UI SETUP ---
st.set_page_config(page_title="AI Chess Reviewer", layout="wide")
st.title("♟️ AI Chess Game Reviewer")

if "analysis_complete" not in st.session_state:
    st.session_state.analysis_complete = False

player_color = st.radio("Your Color:", ("White", "Black"), horizontal=True)
pgn_input = st.text_area("Paste PGN here:", height=150)

# --- BUTTON LOGIC ---
if st.button("Review Game", type="primary"):
    if not pgn_input:
        st.warning("Please paste a game PGN first.")
    else:
        with st.spinner("Stockfish running deep analysis..."):
            moves, rating, acpl, metadata = analyze_game(pgn_input, ENGINE_PATH, player_color)
            
        if moves:
            with st.spinner("AI Coach is drafting your review..."):
                summary, ai_responses = get_coach_comments(moves, player_color)
            
            final_comments = []
            for i, move in enumerate(moves):
                if i < len(ai_responses) and isinstance(ai_responses[i], dict):
                    # --- NEW: We ONLY take the comment. We trust Stockfish's classification! ---
                    final_comments.append(ai_responses[i].get("comment", "No comment provided."))
                else:
                    final_comments.append("Coach had trouble analyzing this move.")
            
            st.session_state.metadata = metadata
            st.session_state.rating = rating
            st.session_state.acpl = acpl
            st.session_state.moves = moves
            st.session_state.comments = final_comments
            st.session_state.game_summary = summary
            st.session_state.analysis_complete = True
            st.session_state.move_index = 0
            
            st.success("Analysis and Coach Review Complete!")


# =========================================================================
# --- INTERACTIVE CHESS BOARD ---
# =========================================================================
if st.session_state.analysis_complete:
    st.divider()
    
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric(label="Estimated Performance Rating", value=f"{st.session_state.rating} ELO")
    with m_col2:
        if "acpl" in st.session_state:
            st.metric(label="Avg. Centipawn Loss (ACPL)", value=f"{st.session_state.acpl}")
    
    st.divider()

    moves = st.session_state.moves
    comments = st.session_state.comments

    # --- MATCH ACCURACY REPORT ---
    st.subheader("📊 Match Accuracy Report")
    cat_colors = {"Brilliant": "green", "Great": "green", "Best": "green", "Excellent": "green", "Good": "green", "Book": "green", "Inaccuracy": "blue", "Mistake": "orange", "Miss": "red", "Blunder": "red"}
    white_counts = {cat: 0 for cat in cat_colors}
    black_counts = {cat: 0 for cat in cat_colors}
    
    for m in moves:
        cat = m.get("classification", "Good")
        if m["turn"] == "White":
            if cat in white_counts: white_counts[cat] += 1
        else:
            if cat in black_counts: black_counts[cat] += 1

    rep_col1, rep_col2 = st.columns(2)
    for col, data in [(rep_col1, white_counts), (rep_col2, black_counts)]:
        with col:
            st.markdown(f"### {'⚪ White' if col == rep_col1 else '⚫ Black'}")
            for cat, count in data.items():
                if count > 0:
                    color = cat_colors.get(cat, "gray")
                    st.markdown(f"- :{color}[**{cat}**]: {count}")
    
    st.divider()

    # --- NAVIGATION CALLBACKS ---
    if "move_index" not in st.session_state:
        st.session_state.move_index = 0

    def go_previous():
        if st.session_state.move_index > 0:
            st.session_state.move_index -= 1

    def go_next():
        if st.session_state.move_index < len(st.session_state.moves):
            st.session_state.move_index += 1

    # --- NEW LAYOUT: Board Left, Text Right ---
    board_col, text_col = st.columns([1.5, 1.2], gap="large")
    
    is_flipped = (player_color == "Black")
    board_size = 600
    sq_size = board_size / 8
    
    wood_colors = {
        'square light': '#F0D9B5', 
        'square dark': '#B58863',
        'margin': '#21201D'
    }

    def draw_player_banner(name_str, clock_sec, is_active):
        bg_color = "#333333" if is_active else "#21201D"
        clock_bg = "#FFFFFF" if is_active else "#555555"
        clock_text = "#000000" if is_active else "#AAAAAA"
        banner = f"""
        <div style="display: flex; justify-content: space-between; align-items: center; 
                    background-color: {bg_color}; padding: 10px 15px; border-radius: 5px; 
                    margin: 5px 0px; color: white; width: {board_size}px; font-family: sans-serif;">
            <div style="font-weight: bold; font-size: 16px;">♟️ {name_str}</div>
            <div style="background-color: {clock_bg}; color: {clock_text}; font-weight: bold; 
                        font-size: 18px; padding: 4px 10px; border-radius: 4px; font-family: monospace;">
                ⏱️ {format_clock(clock_sec)}
            </div>
        </div>
        """
        st.markdown(banner, unsafe_allow_html=True)

    # --- MOVE 0 (STARTING POSITION) ---
    if st.session_state.move_index == 0:
        with board_col:
            top_name = st.session_state.metadata["White"] if is_flipped else st.session_state.metadata["Black"]
            bot_name = st.session_state.metadata["Black"] if is_flipped else st.session_state.metadata["White"]
            draw_player_banner(top_name, None, False)
            board_svg = chess.svg.board(board=chess.Board(), size=board_size, flipped=is_flipped, colors=wood_colors).replace("\n", "")
            st.markdown(f"<div style='width: {board_size}px;'>{board_svg}</div>", unsafe_allow_html=True)
            draw_player_banner(bot_name, None, False)

        with text_col:
            st.subheader("Game Overview")
            st.info(f"**Coach's Summary:**\n\n{st.session_state.game_summary}")

    # --- SPECIFIC MOVE (1+) ---
    else:
        current_move = moves[st.session_state.move_index - 1]
        
        with board_col:
            if is_flipped:
                top_name, top_clk = st.session_state.metadata["White"], current_move.get("w_clk")
                bot_name, bot_clk = st.session_state.metadata["Black"], current_move.get("b_clk")
            else:
                top_name, top_clk = st.session_state.metadata["Black"], current_move.get("b_clk")
                bot_name, bot_clk = st.session_state.metadata["White"], current_move.get("w_clk")
            
            draw_player_banner(top_name, top_clk, is_active=(current_move["turn"] != ("Black" if is_flipped else "White")))
            
            move_obj = chess.Move.from_uci(current_move["uci_move"])
            board_svg = chess.svg.board(board=chess.Board(current_move["fen"]), lastmove=move_obj, size=board_size, flipped=is_flipped, colors=wood_colors).replace("\n", "")
            
            to_sq = move_obj.to_square
            file = chess.square_file(to_sq) 
            rank = 7 - chess.square_rank(to_sq) 
            if is_flipped:
                file = 7 - file
                rank = 7 - rank
                
            left_pos = (file * sq_size) + (sq_size * 0.6)
            top_pos = (rank * sq_size) - (sq_size * 0.2)
            
            cat = current_move.get("classification", "Good")
            icon_path = f"icons/{cat}.png"
            overlay_html = ""
            if os.path.exists(icon_path):
                with open(icon_path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode()
                    overlay_html = f'<img src="data:image/png;base64,{encoded}" style="position: absolute; left: {left_pos}px; top: {top_pos}px; width: 32px; z-index: 10;">'
            
            container_html = f"<div style='position: relative; width: {board_size}px; height: {board_size}px;'>{board_svg}{overlay_html}</div>"
            st.markdown(container_html, unsafe_allow_html=True)
            draw_player_banner(bot_name, bot_clk, is_active=(current_move["turn"] == ("Black" if is_flipped else "White")))

        with text_col:
            st.subheader(f"{current_move['turn']} played:")
            cat = current_move.get("classification", "Good")
            icon_html = get_icon_html(cat)
            
            if icon_html:
                 st.markdown(f"<h1 style='margin-bottom: 5px;'>{icon_html} {cat}</h1>", unsafe_allow_html=True)
            else:
                 color = "🔵"
                 if cat in ["Blunder", "Miss"]: color = "🔴"
                 elif cat in ["Brilliant", "Great", "Best", "Excellent", "Book"]: color = "🟢"
                 elif cat in ["Mistake"]: color = "🟠"
                 st.markdown(f"<h1 style='margin-bottom: 5px;'>{color} {cat}</h1>", unsafe_allow_html=True)
                 
            eval_score = current_move["evaluation"]
            eval_box_html = f"""<div style="display: inline-block; background-color: #2e2e36; border: 1px solid #4a4a5a; border-radius: 6px; padding: 4px 10px; margin-bottom: 15px; font-family: monospace; font-size: 16px; font-weight: bold; color: #e0e0e0;">📈 Eval: {eval_score}</div>"""
            st.markdown(eval_box_html, unsafe_allow_html=True)
            st.markdown(f"### Move: **{current_move['move']}**")
            
            if (st.session_state.move_index - 1) < len(comments):
                st.info(f"**Coach's Tactical Insight:**\n\n{comments[st.session_state.move_index - 1]}")

    # --- NAVIGATION BELOW THE BOARD ---
    with board_col:
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        with nav_col1:
            st.button("⬅️ Prev", on_click=go_previous, disabled=(st.session_state.move_index <= 0), use_container_width=True)
        with nav_col2:
            if st.session_state.move_index == 0:
                st.markdown("<div style='text-align: center; padding-top: 5px; font-weight: bold;'>Start</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: center; padding-top: 5px; font-weight: bold;'>Move {st.session_state.move_index} / {len(moves)}</div>", unsafe_allow_html=True)
        with nav_col3:
            st.button("Next ➡️", on_click=go_next, disabled=(st.session_state.move_index >= len(moves)), use_container_width=True)

    st.divider()
    with st.expander("Show Full Move List"):
        for i, m in enumerate(moves):
            color_tag = "⚪" if m["turn"] == "White" else "⚫"
            status_color = "normal"
            if m["classification"] in ["Blunder", "Miss"]: status_color = "red"
            elif m["classification"] in ["Brilliant", "Great", "Best", "Excellent", "Book"]: status_color = "green"
            elif m["classification"] == "Mistake": status_color = "orange"
            
            bold_prefix = "**👉** " if (i + 1) == st.session_state.move_index else ""
            st.markdown(f"{bold_prefix}**{m['move_number']}. {color_tag} {m['move']}** — :{status_color}[**{m['classification']}**]")