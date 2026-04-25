import streamlit as st
import tempfile
import os
import sys
from pathlib import Path
import time
import json
import glob
from dotenv import load_dotenv

# --- SYSTEM DIAGNOSTICS & SHIELD ---
MISSING_DEPS = []
try:
    import groq
except ImportError: MISSING_DEPS.append("groq")
try:
    import fitz
except ImportError: MISSING_DEPS.append("pymupdf")
try:
    from pydub import AudioSegment
except ImportError: MISSING_DEPS.append("pydub")
try:
    import soundfile
except ImportError: MISSING_DEPS.append("soundfile")

# Load environment variables
load_dotenv()

# --- INITIALIZATION ---
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = None
if 'chapters' not in st.session_state:
    st.session_state.chapters = []
if 'book_loaded' not in st.session_state:
    st.session_state.book_loaded = False
if 'current_progress' not in st.session_state:
    st.session_state.current_progress = 0
if 'current_status' not in st.session_state:
    st.session_state.current_status = "Waiting for upload..."
if 'generated_files' not in st.session_state:
    st.session_state.generated_files = []

# Page Configuration
st.set_page_config(
    page_title="Emotional Audiobook Agent | Kokoro Studio",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- OBSIDIAN RESONANCE DESIGN SYSTEM ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #0b1326;
        --surface: #131b2e;
        --surface-high: #222a3d;
        --primary: #8B5CF6;
        --primary-glow: rgba(139, 92, 246, 0.4);
        --text: #dae2fd;
        --text-muted: #958ea0;
        --glass: rgba(45, 52, 73, 0.4);
        --glass-border: rgba(255, 255, 255, 0.1);
        --radius: 1.5rem;
    }
    .stApp { background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Manrope', sans-serif !important; font-weight: 800 !important; color: white !important; }
    .hero-title { font-size: 3.5rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, white 0%, var(--primary) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .glass-card { background: var(--glass); backdrop-filter: blur(12px); border: 1px solid var(--glass-border); border-radius: var(--radius); padding: 2.5rem; margin-bottom: 2rem; }
    .stButton > button { background: linear-gradient(135deg, var(--primary) 0%, #6d3bd7 100%); color: white !important; border-radius: 50px !important; letter-spacing: 0.1rem; box-shadow: 0 4px 15px var(--primary-glow) !important; width: 100%; transition: all 0.3s ease; }
    .stButton > button:hover { transform: translateY(-3px); box-shadow: 0 8px 25px var(--primary-glow) !important; }
    .diagnostic { background: rgba(255, 107, 107, 0.1); border: 1px solid #ff6b6b; padding: 1.5rem; border-radius: var(--radius); margin-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: CONFIGURATION ---
with st.sidebar:
    st.markdown("<h2 style='color: white;'>⚙️ Configuration</h2>", unsafe_allow_html=True)
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        groq_api_key = st.text_input("GROQ API Key", type="password")
    else:
        st.success("✅ GROQ API Key Active")
    
    model_dir = st.text_input("Model Directory", value="model_assets")
    st.info("💡 Kokoro model runs entirely locally. No API needed!")

# --- MAIN PAGE: HERO ---
st.markdown("<div class='hero-title'>Emotional Audiobook Agent</div>", unsafe_allow_html=True)
st.markdown("<p style='color: var(--text-muted); font-size: 1.2rem;'>Transform PDFs into emotionally intelligent audiobooks powered by Kokoro TTS.</p>", unsafe_allow_html=True)

if MISSING_DEPS:
    st.markdown(f"""<div class='diagnostic'><h3>⚠️ Missing Core Dependencies</h3><p>Run: <code>pip install {" ".join(MISSING_DEPS)}</code></p></div>""", unsafe_allow_html=True)

# --- UI WORKFLOW ---
col_u, col_s = st.columns([1, 1])

with col_u:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<h3>📤 1. Upload Manuscript</h3>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Drop your PDF book here", type=["pdf"])
    if uploaded and not st.session_state.book_loaded:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.getvalue())
            st.session_state.file_path = tmp.name
        if st.button("📖 INITIALIZE STUDIO"):
            with st.spinner("Analyzing manuscript structure..."):
                try:
                    from orchestrator import AudiobookOrchestrator
                    st.session_state.orchestrator = AudiobookOrchestrator(st.session_state.file_path, groq_api_key, model_dir=model_dir)
                    if st.session_state.orchestrator.load_book():
                        st.session_state.chapters = st.session_state.orchestrator.chapters
                        st.session_state.book_loaded = True
                        st.rerun()
                except Exception as e: st.error(f"Error: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

with col_s:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<h3>📚 2. Select Chapters</h3>", unsafe_allow_html=True)
    chapter_numbers = []
    if st.session_state.book_loaded:
        # Show cache status
        cache_status = st.session_state.orchestrator.get_cache_status()
        if cache_status['analysis_from_cache']:
            st.success(f"📖 Analysis from cache (Fast!)")
        
        # Option to clear cache
        col_ch, col_clr = st.columns([3, 1])
        with col_clr:
            if st.button("🔄 Re-Analyze", help="Clear cache and re-analyze the book"):
                st.session_state.orchestrator.clear_analysis_cache()
                st.info("Cache cleared! Re-upload to analyze fresh.")
        
        mode = col_ch.radio("Selection", ["All", "Range"], horizontal=True)
        total = len(st.session_state.chapters)
        if mode == "All": chapter_numbers = list(range(1, total + 1))
        else:
            c1, c2 = st.columns(2)
            s_ch = c1.number_input("Start", 1, total, 1)
            e_ch = c2.number_input("End", s_ch, total, min(10, total))
            chapter_numbers = list(range(int(s_ch), int(e_ch) + 1))
    else: st.write("Initialize a book to continue.")
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.book_loaded and chapter_numbers:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>🎬 3. Synthesize Generative Voices</h3>", unsafe_allow_html=True)
    st.progress(st.session_state.current_progress)
    st.markdown(f"<p style='text-align: center; color: var(--primary);'>{st.session_state.current_status}</p>", unsafe_allow_html=True)
    if st.button("🔥 GENERATE AUDIO"):
        try:
            def up_p(p): st.session_state.current_progress = p
            def up_s(s): st.session_state.current_status = s
            st.session_state.orchestrator.set_progress_callbacks(up_p, up_s)
            st.session_state.orchestrator.analyze_characters()
            generated = st.session_state.orchestrator.generate_chapters(chapter_numbers)
            st.session_state.generated_files = generated
            st.rerun()
        except Exception as e: st.error(f"Synthesis failed: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.generated_files:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<h3>📥 4. Studio Gallery</h3>", unsafe_allow_html=True)
    mp3s = [f for f in st.session_state.generated_files if str(f).endswith('.mp3')]
    grid = st.columns(3)
    for i, file in enumerate(sorted(mp3s)):
        with grid[i % 3]:
            st.markdown(f"**{Path(file).stem}**")
            with open(file, "rb") as af:
                st.audio(af.read(), format="audio/mp3")
                st.download_button("💾 Save", af, file_name=Path(file).name, key=f"dl_{i}")
    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("� Smart Analysis Caching"):
    st.markdown("""
    **How It Works:**
    - ✅ First upload: Analyzes chapters and characters (may take 1-2 minutes)
    - ✅ Second upload (same book): Loads cached analysis instantly
    - ✅ No re-analysis needed: Go straight to audio generation
    
    **Cache Features:**
    - Automatic detection of the same book (using file hash)
    - One-click "Re-Analyze" button to clear cache if needed
    - Fast incremental generation for additional chapters
    """)
    
    # Show cache statistics (only if orchestrator exists)
    if st.session_state.orchestrator:
        all_cached = st.session_state.orchestrator.get_all_cached_books()
        if all_cached and all_cached.get('total_cached_books', 0) > 0:
            st.info(f"📊 **Cached Books:** {all_cached['total_cached_books']}")
            for book in all_cached.get('cached_books', []):
                st.text(f"  • {book['name']}: {book['chapters']} chapters, {book['characters']} characters")
    else:
        st.caption("Upload a book to see cache statistics")