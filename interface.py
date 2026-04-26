import streamlit as st
import tempfile
import os
import sys
from pathlib import Path
import time
import json
import glob
import warnings
import logging
from dotenv import load_dotenv

# Suppress noisy library warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message="Accessing __path__ from")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

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
if 'book_loaded' not in st.session_state: st.session_state.book_loaded = False
if 'chapter_selection_done' not in st.session_state: st.session_state.chapter_selection_done = False
if 'selected_chapters' not in st.session_state: st.session_state.selected_chapters = []
if 'analysis_started' not in st.session_state: st.session_state.analysis_started = False
if 'characters_analysed' not in st.session_state: st.session_state.characters_analysed = False
if 'generation_started' not in st.session_state: st.session_state.generation_started = False
if 'generated_files' not in st.session_state: st.session_state.generated_files = []
if 'current_progress' not in st.session_state: st.session_state.current_progress = 0
if 'current_status' not in st.session_state: st.session_state.current_status = "Waiting..."
# Page Configuration
st.set_page_config(page_title="BooksTalk", page_icon="🎧", layout="wide", initial_sidebar_state="expanded")

# --- BOOKSTALK: MIDNIGHT BLOOM + AURORA NEBULA ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* { font-family: 'Inter', sans-serif !important; }
.stApp { background-color: #080d1a !important; color: #f0f4ff; }
.stApp::before {
  content: '';
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse 700px 320px at 55% 0%, rgba(192,38,211,0.11) 0%, transparent 70%),
    radial-gradient(ellipse 500px 260px at 100% 30%, rgba(56,189,248,0.07) 0%, transparent 70%),
    radial-gradient(ellipse 420px 200px at 50% 90%, rgba(240,18,122,0.06) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}
section[data-testid="stSidebar"] { background-color: #060a14 !important; border-right: 1px solid rgba(255,255,255,0.06) !important; }
.stButton > button {
  background: #f0127a !important; color: #fff !important; border: none !important;
  border-radius: 50px !important; padding: 12px 32px !important;
  font-size: 14px !important; font-weight: 600 !important; letter-spacing: 0.02em !important;
  width: auto !important; transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.88; }
.bt-card { background: rgba(10,14,30,0.70); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 18px 16px; margin-bottom: 12px; }
.bt-section-label { font-size: 11px; letter-spacing: 0.14em; color: #5a6a90; text-transform: uppercase; margin-bottom: 6px; }
.wbar { width: 4px; background: #f0127a; border-radius: 2px; animation: wbpulse 0.8s ease-in-out infinite alternate; }
@keyframes wbpulse { from { height: 6px; } to { height: 28px; } }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div style='padding:16px 4px 20px;'>
      <span style='font-size:20px;font-weight:700;color:#f0f4ff;'>Books</span><span style='font-size:20px;font-weight:700;color:#f0127a;'>Talk</span>
    </div>
    <div style='font-size:10px;letter-spacing:0.12em;color:#3a4460;text-transform:uppercase;padding:0 4px 6px;'>Workspace</div>
    """, unsafe_allow_html=True)
    for label in ["New Project", "My Library", "Export History"]:
        is_active = label == "New Project"
        bg = "rgba(240,18,122,0.10)" if is_active else "transparent"
        clr = "#f0127a" if is_active else "#5a6a90"
        bl = "2px solid #f0127a" if is_active else "2px solid transparent"
        st.markdown(f"<div style='font-size:13px;color:{clr};background:{bg};padding:9px 12px;border-radius:8px;border-left:{bl};margin-bottom:3px;cursor:pointer;'>{label}</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:10px;letter-spacing:0.12em;color:#3a4460;text-transform:uppercase;padding:14px 4px 6px;'>Settings</div>", unsafe_allow_html=True)
    for label in ["Voice Profiles", "API Keys"]:
        st.markdown(f"<div style='font-size:13px;color:#5a6a90;padding:9px 12px;border-radius:8px;margin-bottom:3px;cursor:pointer;'>{label}</div>", unsafe_allow_html=True)
    st.markdown("<div style='margin:10px 0;'></div>", unsafe_allow_html=True)
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if groq_api_key:
        st.markdown("""<div style='padding:10px 12px;background:rgba(10,18,10,0.7);border-radius:8px;border:1px solid #1a2e1a;font-size:11px;color:#4a8a40;'><span style='display:inline-block;width:6px;height:6px;border-radius:50%;background:#22c55e;margin-right:6px;'></span>Groq API connected</div>""", unsafe_allow_html=True)
    else:
        groq_api_key = st.text_input("GROQ API Key", type="password")
    st.markdown("<div style='margin:8px 0;'></div>", unsafe_allow_html=True)
    model_dir = st.text_input("Model Directory", value="model_assets")
    
    st.markdown("<div style='margin-top:20px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 20px;'></div>", unsafe_allow_html=True)
    reset_trigger = st.button("🗑️ Clear All Cache & Reset")
    if reset_trigger:
        # Clear directories
        for d in ["analysis_cache", "voice_cache", "audiobook_output"]:
            if os.path.exists(d):
                for f in os.listdir(d):
                    try: os.remove(os.path.join(d, f))
                    except: pass
        
        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
            
        st.success("All cache cleared! Restarting...")
        time.sleep(1)
        st.rerun()

# --- MISSING DEPS BANNER ---
if MISSING_DEPS:
    st.markdown(f"""<div style='background:rgba(240,18,122,0.08);border:1px solid rgba(240,18,122,0.3);border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#f0127a;'>⚠ Missing dependencies — run: <code style='background:rgba(0,0,0,0.3);padding:2px 6px;border-radius:4px;'>pip install {" ".join(MISSING_DEPS)}</code></div>""", unsafe_allow_html=True)

# --- STEPPER ---
def _step_html(steps, active):
    parts = []
    for i, label in enumerate(steps):
        n = i + 1
        done = n < active
        curr = n == active
        if done:
            circ = f"<div style='width:28px;height:28px;border-radius:50%;background:#f0127a;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0;'>{n}</div>"
            lclr = "#f0127a"
        elif curr:
            circ = f"<div style='width:28px;height:28px;border-radius:50%;border:2px solid #f0127a;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#f0127a;flex-shrink:0;'>{n}</div>"
            lclr = "#f0f4ff"
        else:
            circ = f"<div style='width:28px;height:28px;border-radius:50%;border:2px solid #1e2540;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#2a3450;flex-shrink:0;'>{n}</div>"
            lclr = "#2a3450"
        parts.append(f"<div style='display:flex;flex-direction:column;align-items:center;gap:6px;'>{circ}<span style='font-size:10px;color:{lclr};white-space:nowrap;'>{label}</span></div>")
        if i < len(steps)-1:
            lc = "#f0127a" if done else "#1e2540"
            parts.append(f"<div style='flex:1;height:2px;background:{lc};margin-bottom:14px;'></div>")
    return "<div style='display:flex;align-items:center;gap:8px;padding:24px 0 28px;'>" + "".join(parts) + "</div>"

_steps = ["Upload","Chapters","Analyse","Characters","Generate","Listen"]
if not st.session_state.book_loaded: _active = 1
elif not st.session_state.get('chapter_selection_done'): _active = 2
elif not st.session_state.get('analysis_started'): _active = 3
elif not st.session_state.characters_analysed: _active = 4
elif not st.session_state.generated_files: _active = 5
else: _active = 6
st.markdown(_step_html(_steps, _active), unsafe_allow_html=True)

# --- STEP 1: UPLOAD ---
if not st.session_state.book_loaded:
    st.markdown("""<div style='font-size:11px;letter-spacing:0.14em;color:#5a4a70;text-transform:uppercase;margin-bottom:8px;'>New project — step 1 of 5</div>
<div style='font-size:26px;font-weight:700;letter-spacing:-0.02em;color:#f0f4ff;margin-bottom:6px;'>Upload your manuscript</div>
<div style='font-size:14px;color:#5a6a90;margin-bottom:24px;'>Drop a PDF and we'll detect characters, assign voices, and craft your audiobook.</div>""", unsafe_allow_html=True)
    uploaded = st.file_uploader("PDF manuscript", type=["pdf"], label_visibility="collapsed")
    if uploaded:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.getvalue())
            st.session_state.file_path = tmp.name
        sz = f"{len(uploaded.getvalue())//1024} KB"
        st.markdown(f"""<div style='background:rgba(12,17,40,0.8);border:1px solid rgba(240,18,122,0.2);border-radius:10px;padding:12px 16px;display:flex;align-items:center;gap:12px;margin-bottom:22px;'><div style='width:7px;height:7px;border-radius:50%;background:#f0127a;flex-shrink:0;'></div><div><div style='font-size:13px;color:#e2e8f8;font-weight:500;'>{uploaded.name}</div><div style='font-size:11px;color:#3a4460;'>{sz} · PDF · Ready</div></div></div>""", unsafe_allow_html=True)
        if st.button("Analyse manuscript"):
            with st.spinner("Analysing manuscript structure…"):
                try:
                    from orchestrator import AudiobookOrchestrator
                    st.session_state.orchestrator = AudiobookOrchestrator(st.session_state.file_path, groq_api_key, model_dir=model_dir)
                    if st.session_state.orchestrator.load_book():
                        st.session_state.chapters = st.session_state.orchestrator.chapters
                        st.session_state.book_loaded = True
                        st.rerun()
                except Exception as e: st.error(f"Error: {e}")

# --- STEP 2: SELECT CHAPTERS ---
if st.session_state.book_loaded and not st.session_state.get('chapter_selection_done'):
    st.markdown("<div style='font-size:26px;font-weight:700;color:#f0f4ff;margin-bottom:16px;'>Select chapters</div>", unsafe_allow_html=True)
    if st.session_state.orchestrator:
        cache_status = st.session_state.orchestrator.get_cache_status()
        if cache_status.get('analysis_from_cache'):
            st.markdown("<div style='font-size:12px;color:#4a8a40;margin-bottom:12px;'>⚡ Analysis loaded from cache</div>", unsafe_allow_html=True)
    
    total = len(st.session_state.chapters)
    col_sel1, col_sel2 = st.columns([1, 1])
    with col_sel1:
        select_all = st.button("Select All")
    with col_sel2:
        deselect_all = st.button("Deselect All")
        
    if select_all: st.session_state.selected_temp = list(range(1, total + 1))
    if deselect_all: st.session_state.selected_temp = []
    
    if 'selected_temp' not in st.session_state:
        st.session_state.selected_temp = []

    # Scrollable container for chapters
    selected = []
    st.markdown('<div style="max-height: 400px; overflow-y: auto; background: rgba(0,0,0,0.2); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05);">', unsafe_allow_html=True)
    for i, ch in enumerate(st.session_state.chapters, 1):
        title = ch.get('title', f"Chapter {i}")
        is_checked = i in st.session_state.selected_temp
        chk = st.checkbox(f"{i}. {title}", value=is_checked, key=f"chk_{i}")
        if chk: selected.append(i)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.session_state.selected_temp = selected
    
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    if st.button("Confirm Selection →"):
        if not selected:
            st.warning("Please select at least one chapter.")
        else:
            st.session_state.selected_chapters = selected
            st.session_state.chapter_selection_done = True
            st.rerun()

# --- STEP 3: ANALYSE SELECTION ---
if st.session_state.get('chapter_selection_done') and not st.session_state.get('analysis_started'):
    st.markdown("<div style='font-size:26px;font-weight:700;color:#f0f4ff;margin-bottom:6px;'>Analysing selection...</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:14px;color:#5a6a90;margin-bottom:24px;'>We are identifying characters and mapping voices for Chapters: {st.session_state.selected_chapters}</div>", unsafe_allow_html=True)
    
    if st.button("Start Deep Analysis"):
        # Pre-check text length
        selected_text = ""
        for num in st.session_state.selected_chapters:
            idx = num - 1
            if 0 <= idx < len(st.session_state.chapters):
                selected_text += st.session_state.chapters[idx].get('content', '')
        
        if len(selected_text.strip()) < 10:
            st.error("❌ No text could be extracted from these chapters. Is your PDF image-only (scanned)?")
            st.info("Try selecting different chapters or a different PDF.")
        else:
            st.session_state.analysis_started = True
            with st.status("Performing deep analysis...", expanded=True) as status:
                def up_p(p): st.session_state.current_progress = p
                def up_s(s): st.session_state.current_status = s
                st.session_state.orchestrator.set_progress_callbacks(up_p, up_s)
                
                if st.session_state.orchestrator.analyze_characters_for_selection(st.session_state.selected_chapters):
                    st.session_state.characters_analysed = True
                    status.update(label="Analysis complete!", state="complete")
                    st.rerun()
                else:
                    st.error("Analysis failed. Check logs.")
                    st.session_state.analysis_started = False
    
    if st.button("← Back to Chapters"):
        st.session_state.chapter_selection_done = False
        st.rerun()

# --- STEP 4: CHARACTERS ---
if st.session_state.characters_analysed and not st.session_state.get('generation_started'):
    st.markdown("<div style='font-size:26px;font-weight:700;color:#f0f4ff;margin-bottom:6px;'>Characters in Selection</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:14px;color:#5a6a90;margin-bottom:24px;'>Verify the voices assigned to each character.</div>", unsafe_allow_html=True)
    
    registry = st.session_state.orchestrator.character_registry
    voice_map = st.session_state.orchestrator.voice_map
    
    cols3 = st.columns(3)
    for idx, (name, data) in enumerate(registry.items()):
        voice_name = voice_map.get(name, "Unknown")
        with cols3[idx % 3]:
            st.markdown(f"""
            <div class='bt-card'>
                <div style='font-size:16px;color:#f0f4ff;font-weight:700;margin-bottom:4px;'>{name}</div>
                <div style='font-size:10px;color:#f0127a;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>{voice_name}</div>
                <div style='font-size:12px;color:#5a6a90;'>{data.get('personality', 'No description')}</div>
            </div>
            """, unsafe_allow_html=True)
    
    col_btns = st.columns([1, 4])
    with col_btns[0]:
        if st.button("← Back"):
            st.session_state.analysis_started = False
            st.session_state.characters_analysed = False
            st.rerun()
    with col_btns[1]:
        if st.button("Generate Audiobook →"):
            st.session_state.generation_started = True
            st.rerun()

# --- STEP 5: GENERATE ---
if st.session_state.get('generation_started') and not st.session_state.generated_files:
    st.markdown("<div style='font-size:26px;font-weight:700;color:#f0f4ff;margin-bottom:6px;'>Generating Audio...</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:13px;color:#f0127a;margin-bottom:8px;'>{st.session_state.current_status}</div>", unsafe_allow_html=True)
    st.progress(st.session_state.current_progress)
    st.markdown("""<div style='display:flex;align-items:flex-end;gap:3px;height:32px;margin:16px 0;'><div class='wbar' style='animation-delay:0s'></div><div class='wbar' style='animation-delay:0.1s'></div><div class='wbar' style='animation-delay:0.2s'></div><div class='wbar' style='animation-delay:0.3s'></div><div class='wbar' style='animation-delay:0.4s'></div></div>""", unsafe_allow_html=True)
    
    # Auto-trigger generation
    try:
        def up_p(p): st.session_state.current_progress = p
        def up_s(s): st.session_state.current_status = s
        st.session_state.orchestrator.set_progress_callbacks(up_p, up_s)
        generated = st.session_state.orchestrator.generate_chapters(st.session_state.selected_chapters)
        st.session_state.generated_files = generated
        st.rerun()
    except Exception as e:
        st.error(f"Synthesis failed: {e}")
        st.session_state.generation_started = False
    
    if st.button("← Stop & Go Back"):
        st.session_state.generation_started = False
        st.rerun()

# --- STEP 5: GALLERY ---
if st.session_state.generated_files:
    audio_files = [f for f in st.session_state.generated_files if str(f).endswith('.mp3') or str(f).endswith('.wav')]
    voices_used = len(set(Path(f).stem.split('_')[0] for f in audio_files)) if audio_files else 0
    total_chapters = len(audio_files)
    st.markdown(f"""<div style='display:flex;gap:12px;margin-bottom:26px;'><div style='background:rgba(10,14,30,0.7);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:14px 20px;flex:1;'><div style='font-size:22px;font-weight:700;color:#f0127a;'>{total_chapters}</div><div style='font-size:10px;color:#3a4460;letter-spacing:0.1em;text-transform:uppercase;'>Chapters</div></div><div style='background:rgba(10,14,30,0.7);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:14px 20px;flex:1;'><div style='font-size:22px;font-weight:700;color:#f0127a;'>{voices_used}</div><div style='font-size:10px;color:#3a4460;letter-spacing:0.1em;text-transform:uppercase;'>Voices Used</div></div><div style='background:rgba(10,14,30,0.7);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:14px 20px;flex:1;'><div style='font-size:22px;font-weight:700;color:#f0127a;'>✓</div><div style='font-size:10px;color:#3a4460;letter-spacing:0.1em;text-transform:uppercase;'>Ready</div></div></div>""", unsafe_allow_html=True)
    if not audio_files:
        st.warning("No audio files generated yet.")
    for i, file in enumerate(sorted(audio_files)):
        stem = Path(file).stem
        fmt = "audio/mp3" if str(file).endswith('.mp3') else "audio/wav"
        _bar_parts = []
        for j in range(10):
            _clr = "#f0127a" if j % 2 == 0 else "rgba(240,18,122,0.2)"
            _ht = 8 + ((j * 7) % 16)
            _bar_parts.append(f"<div style='width:3px;background:{_clr};border-radius:2px;height:{_ht}px;'></div>")
        bars = "".join(_bar_parts)
        st.markdown(f"""<div style='background:rgba(10,14,30,0.65);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 20px;display:flex;align-items:center;gap:14px;margin-bottom:10px;'><span style='font-size:11px;color:#3a4460;width:64px;'>Chapter {i+1}</span><span style='font-size:14px;color:#c8d4f0;font-weight:500;flex:1;'>{stem}</span><div style='display:flex;align-items:flex-end;gap:2px;'>{bars}</div><span style='font-size:11px;color:#3a4460;width:40px;text-align:right;'>--:--</span></div>""", unsafe_allow_html=True)
        with open(file, "rb") as af:
            data = af.read()
            c1, c2 = st.columns([1,1])
            with c1: st.audio(data, format=fmt)
            with c2: st.download_button("↓ Save", data, file_name=Path(file).name, key=f"dl_{i}")
    
    st.markdown("<div style='margin-top:32px;'></div>", unsafe_allow_html=True)
    if st.button("➕ Add More Chapters / Modify Selection"):
        st.session_state.chapter_selection_done = False
        st.session_state.analysis_started = False
        st.session_state.characters_analysed = False
        st.session_state.generation_started = False
        st.session_state.generated_files = []
        st.rerun()

with st.expander("⚡ Smart Analysis Caching"):
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