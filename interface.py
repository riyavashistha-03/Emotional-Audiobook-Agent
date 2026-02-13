import streamlit as st
import tempfile
import os
from pathlib import Path
import time
import json
import glob
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set page config must be the first Streamlit command
st.set_page_config(
    page_title="Emotional Audiobook Studio",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = None
if 'chapters' not in st.session_state:
    st.session_state.chapters = []
if 'generated_files' not in st.session_state:
    st.session_state.generated_files = []
if 'current_progress' not in st.session_state:
    st.session_state.current_progress = 0
if 'current_status' not in st.session_state:
    st.session_state.current_status = "Ready"
if 'book_loaded' not in st.session_state:
    st.session_state.book_loaded = False
if 'file_path' not in st.session_state:
    st.session_state.file_path = None

# Custom CSS for modern look with bright and muted colors
st.markdown("""
<style>
    /* Main background with gradient */
    .stApp {
        background: linear-gradient(135deg, #f5f0e8 0%, #e8dfd3 100%);
    }
    
    /* Headers */
    h1 {
        color: #4a3b2f !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.5px !important;
    }
    
    h2, h3 {
        color: #5c4b3a !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(90deg, #ff7e5f 0%, #feb47b 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 50px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(255, 126, 95, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 126, 95, 0.4);
    }
    
    /* Secondary button */
    .stButton > button[kind="secondary"] {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* File uploader */
    .stFileUploader {
        border: 2px dashed #c4b5a0;
        border-radius: 15px;
        padding: 1rem;
        background: rgba(255, 255, 255, 0.5);
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #ff7e5f 0%, #feb47b 100%);
    }
    
    /* Success messages */
    .stSuccess {
        background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
        color: #2c3e50;
        border: none;
        border-radius: 10px;
        padding: 1rem;
    }
    
    /* Info boxes */
    .stInfo {
        background: rgba(255, 255, 255, 0.7);
        border-left: 5px solid #ff7e5f;
        color: #4a3b2f;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
    }
    
    /* Audio player */
    audio {
        width: 100%;
        border-radius: 30px;
        margin: 1rem 0;
    }
    
    /* Cards for chapters */
    .chapter-card {
        background: white;
        border-radius: 15px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border: 1px solid rgba(196, 181, 160, 0.3);
    }
    
    /* Colorful accents */
    .accent-1 {
        color: #ff7e5f;
    }
    .accent-2 {
        color: #667eea;
    }
    .accent-3 {
        color: #84fab0;
    }
    
    /* Dividers */
    hr {
        background: linear-gradient(90deg, transparent, #c4b5a0, transparent);
        height: 2px;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# Header
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("<h1 style='text-align: center;'>🎧 Emotional Audiobook Studio</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6b5a48;'>Transform your PDF books into narrated audiobooks with AI-generated character voices</p>", unsafe_allow_html=True)

st.markdown("---")

# Sidebar configuration
with st.sidebar:
    st.markdown("<h2 style='color: #4a3b2f;'>🎛️ Configuration</h2>", unsafe_allow_html=True)
    
    # Check if API key is available from environment
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if groq_api_key:
        st.success("✅ GROQ API key found in environment")
        # Optional: Allow override
        with st.expander("Override API Key (optional)"):
            override_key = st.text_input("Alternative GROQ API Key", type="password")
            if override_key:
                groq_api_key = override_key
                os.environ["GROQ_API_KEY"] = override_key
                st.success("✅ Using override key")
    else:
        st.warning("⚠️ GROQ API key not found in environment")
        groq_api_key = st.text_input("Enter GROQ API Key", type="password", 
                                     help="Get one from console.groq.com")
        if groq_api_key:
            os.environ["GROQ_API_KEY"] = groq_api_key
            st.success("✅ API key saved for this session")
    
    # Create .env file helper
    if not os.path.exists(".env") and groq_api_key:
        if st.button("💾 Save to .env file (permanent)"):
            with open(".env", "w") as f:
                f.write(f"GROQ_API_KEY={groq_api_key}\n")
                f.write("# MOSS-TTS URL (default: localhost)\n")
                f.write("MOSS_API_URL=http://localhost:7860\n")
            st.success("✅ Saved to .env file! Future sessions will auto-load.")
            st.rerun()
    
    # MOSS API URL (also from env or default)
    moss_api_url = os.getenv("MOSS_API_URL", "http://localhost:7860")
    moss_api_url = st.text_input("MOSS-TTS API URL", value=moss_api_url,
                                 help="URL where MOSS-TTS is running")
    
    # Mock mode for testing
    use_mock = st.checkbox("🧪 Mock Mode (Test without MOSS)", value=True,
                          help="Use mock voices for testing when MOSS is not available")
    
    if use_mock:
        st.info("Mock Mode: Using simulated voices for testing")
    
    st.markdown("---")
    
    # Book stats
    if st.session_state.chapters:
        st.markdown(f"<h3>📊 Book Stats</h3>", unsafe_allow_html=True)
        st.markdown(f"**Chapters:** {len(st.session_state.chapters)}")
        if st.session_state.generated_files:
            st.markdown(f"**Generated:** {len(st.session_state.generated_files)} files")
    
    st.markdown("---")
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1rem; border-radius: 15px; color: white;'>
        <h4 style='color: white; margin-top: 0;'>🎯 How it works</h4>
        <ol style='margin-bottom: 0;'>
            <li>Upload your PDF book</li>
            <li>AI analyzes characters & voices</li>
            <li>MOSS generates unique voices</li>
            <li>Scene-by-scene narration</li>
            <li>Download your audiobook</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

# Main content area
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("<h2>📤 1. Upload Your Book</h2>", unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"], 
                                     help="Select a text-based PDF book")
    
    if uploaded_file and not st.session_state.book_loaded:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            st.session_state.file_path = tmp_file.name
        
        st.success(f"✅ Uploaded: {uploaded_file.name}")
        
        # Load book button
        if st.button("📖 Load & Analyze Book", use_container_width=True):
            if not groq_api_key and not use_mock:
                st.error("Please enter your GROQ API key first or enable Mock Mode!")
            else:
                with st.spinner("Loading book and detecting chapters..."):
                    try:
                        # Use mock key if in mock mode
                        actual_api_key = groq_api_key if groq_api_key else "mock_key"
                        
                        from orchestrator import AudiobookOrchestrator
                        
                        # Initialize orchestrator
                        st.session_state.orchestrator = AudiobookOrchestrator(
                            pdf_path=st.session_state.file_path,
                            groq_api_key=actual_api_key,
                            moss_api_url=moss_api_url
                        )
                        
                        # Load book
                        if st.session_state.orchestrator.load_book():
                            st.session_state.chapters = st.session_state.orchestrator.chapters
                            st.session_state.book_loaded = True
                            st.success(f"✅ Found {len(st.session_state.chapters)} chapters")
                            st.rerun()
                        else:
                            st.error("Failed to load book. Please check the PDF format.")
                    except Exception as e:
                        st.error(f"Error loading book: {str(e)}")

with col2:
    if st.session_state.chapters:
        st.markdown("<h2>📚 2. Select Chapters</h2>", unsafe_allow_html=True)
        
        total_chapters = len(st.session_state.chapters)
        
        # Chapter selection options
        selection_mode = st.radio(
            "Selection Mode",
            ["All Chapters", "Range", "Specific"],
            horizontal=True
        )
        
        chapter_numbers = []
        
        if selection_mode == "All Chapters":
            chapter_numbers = list(range(1, total_chapters + 1))
            st.info(f"📚 Will process all {total_chapters} chapters")
            
        elif selection_mode == "Range":
            col_a, col_b = st.columns(2)
            with col_a:
                start = st.number_input("Start Chapter", min_value=1, max_value=total_chapters, value=1)
            with col_b:
                end = st.number_input("End Chapter", min_value=start, max_value=total_chapters, value=min(10, total_chapters))
            
            chapter_numbers = list(range(start, end + 1))
            st.info(f"📖 Selected chapters: {start} to {end}")
            
        else:  # Specific
            chapter_input = st.text_input("Enter chapter numbers (e.g., 1,3,5-7)", value="1")
            
            # Parse input
            try:
                numbers = set()
                parts = chapter_input.replace(' ', '').split(',')
                for part in parts:
                    if '-' in part:
                        s, e = map(int, part.split('-'))
                        numbers.update(range(s, e + 1))
                    else:
                        numbers.add(int(part))
                
                chapter_numbers = sorted([n for n in numbers if 1 <= n <= total_chapters])
                st.info(f"📖 Selected: {', '.join(map(str, chapter_numbers[:10]))}{'...' if len(chapter_numbers) > 10 else ''}")
            except:
                st.error("Invalid format. Use: 1,3,5-7")
                chapter_numbers = []
        
        # Show chapter preview
        with st.expander("📋 Chapter Preview"):
            for i, chapter in enumerate(st.session_state.chapters[:5]):
                title = chapter.get('title', f'Chapter {i+1}')
                preview = chapter.get('content', '')[:100] + "..."
                st.markdown(f"""
                <div class="chapter-card">
                    <strong>{title}</strong><br>
                    <span style='color: #6b5a48; font-size: 0.9rem;'>{preview}</span>
                </div>
                """, unsafe_allow_html=True)
            if len(st.session_state.chapters) > 5:
                st.markdown(f"*... and {len(st.session_state.chapters) - 5} more chapters*")

# Progress and generation section
if st.session_state.chapters and chapter_numbers:
    st.markdown("---")
    st.markdown("<h2 style='text-align: center;'>🎬 3. Generate Audiobook</h2>", unsafe_allow_html=True)
    
    # Progress display
    progress_col, status_col = st.columns([3, 1])
    
    with progress_col:
        progress_bar = st.progress(st.session_state.current_progress)
    with status_col:
        status_text = st.empty()
        status_text.info(st.session_state.current_status)
    
    # Generate button
    if st.button("🎬 GENERATE AUDIOBOOK", type="primary", use_container_width=True):
        if not groq_api_key and not use_mock:
            st.error("Please enter your GROQ API key first or enable Mock Mode!")
        else:
            try:
                # Update progress callback
                def update_progress(progress):
                    st.session_state.current_progress = progress
                    progress_bar.progress(progress)
                
                def update_status(status):
                    st.session_state.current_status = status
                    status_text.info(status)
                
                st.session_state.orchestrator.set_progress_callbacks(
                    update_progress, update_status
                )
                
                # Step 1: Character analysis
                update_status("🔍 Analyzing characters...")
                if not st.session_state.orchestrator.analyze_characters():
                    st.error("Character analysis failed. Please check your API key.")
                    st.stop()
                
                # Step 2: Generate selected chapters
                update_status("🎭 Generating voices and scenes...")
                generated = st.session_state.orchestrator.generate_chapters(
                    chapter_numbers,
                    use_mock=use_mock
                )
                
                st.session_state.generated_files = generated
                
                # Final progress
                update_progress(1.0)
                update_status("✅ Complete!")
                
                st.success(f"✅ Successfully generated {len(generated)} chapters!")
                
                # Show manifest button
                st.session_state.orchestrator.save_manifest()
                
            except Exception as e:
                st.error(f"Error during generation: {str(e)}")
                st.exception(e)
    
    # Results display
    if st.session_state.generated_files:
        st.markdown("---")
        st.markdown("<h2>📥 4. Download Your Audiobook</h2>", unsafe_allow_html=True)
        
        # Find combined file first
        combined_files = [f for f in st.session_state.generated_files if 'complete' in f or 'chapters' in f]
        
        if combined_files:
            latest_combined = max(combined_files, key=os.path.getctime)
            
            st.markdown("### 🎧 Complete Audiobook")
            with open(latest_combined, "rb") as f:
                audio_bytes = f.read()
            
            st.audio(audio_bytes, format="audio/mp3")
            
            col_d1, col_d2, col_d3 = st.columns([1,1,1])
            with col_d2:
                st.download_button(
                    label="📥 Download Complete Audiobook",
                    data=audio_bytes,
                    file_name=os.path.basename(latest_combined),
                    mime="audio/mp3",
                    use_container_width=True
                )
        
        # Individual chapters
        st.markdown("### 📚 Individual Chapters")
        chapter_files = [f for f in st.session_state.generated_files if 'chapter_' in f and f.endswith('.mp3')]
        
        # Display in a grid
        cols = st.columns(3)
        for i, chapter_file in enumerate(sorted(chapter_files)):
            with cols[i % 3]:
                chapter_name = os.path.basename(chapter_file).replace('.mp3', '')
                with open(chapter_file, "rb") as f:
                    audio_bytes = f.read()
                
                st.audio(audio_bytes, format="audio/mp3")
                st.download_button(
                    label=f"Download {chapter_name}",
                    data=audio_bytes,
                    file_name=os.path.basename(chapter_file),
                    mime="audio/mp3",
                    key=f"download_{i}",
                    use_container_width=True
                )

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6b5a48; padding: 2rem;'>
    <p>🎧 Emotional Audiobook Studio | Powered by GROQ Llama 3.3 + MOSS-TTS</p>
    <p style='font-size: 0.9rem;'>Free and open-source | Create professional audiobooks with AI-generated character voices</p>
</div>
""", unsafe_allow_html=True)

# Instructions expander (moved to bottom)
# Instructions expander - FIXED for visibility
with st.expander("📋 How to get started</span>"):
    st.markdown("""
    "<span style='color: #ff7e5f;'>Detailed instructions below:</span>", unsafe_allow_html=True
    <div style='background-color: white; padding: 1rem; border-radius: 10px; color: #2c3e50;'>
        <ol style='color: #2c3e50; margin-bottom: 0; padding-left: 1.5rem;'>
            <li><strong style='color: #4a3b2f;'>Get a GROQ API key (if not using Mock Mode):</strong>
                <ul style='margin-top: 0.5rem; margin-bottom: 1rem; color: #2c3e50;'>
                    <li>Go to <a href='https://console.groq.com' style='color: #ff7e5f; text-decoration: none;'>console.groq.com</a></li>
                    <li>Sign up for a free account</li>
                    <li>Get your API key from the API Keys section</li>
                    <li>Save it in <code style='background: #f0f0f0; color: #e83e8c; padding: 0.2rem 0.4rem; border-radius: 4px;'>.env</code> file for automatic loading</li>
                </ul>
            </li>
            <li><strong style='color: #4a3b2f;'>Set up MOSS-TTS (optional, for real voices):</strong>
                <ul style='margin-top: 0.5rem; margin-bottom: 1rem; color: #2c3e50;'>
                    <li>Run <code style='background: #f0f0f0; color: #e83e8c; padding: 0.2rem 0.4rem; border-radius: 4px;'>./deploy_moss.sh</code> to set up locally</li>
                    <li>Or use a cloud GPU service</li>
                    <li>Keep <strong style='color: #ff7e5f;'>Mock Mode</strong> enabled to test without MOSS</li>
                </ul>
            </li>
            <li><strong style='color: #4a3b2f;'>Upload your PDF:</strong>
                <ul style='margin-top: 0.5rem; margin-bottom: 1rem; color: #2c3e50;'>
                    <li>Make sure it's a text-based PDF (not scanned)</li>
                    <li>The book should have clear chapter headings</li>
                </ul>
            </li>
            <li><strong style='color: #4a3b2f;'>Wait for processing:</strong>
                <ul style='margin-top: 0.5rem; margin-bottom: 1rem; color: #2c3e50;'>
                    <li>Character analysis takes 1-2 minutes</li>
                    <li>Each chapter takes 2-3 minutes to generate</li>
                </ul>
            </li>
            <li><strong style='color: #4a3b2f;'>Download your audiobook:</strong>
                <ul style='margin-top: 0.5rem; margin-bottom: 0; color: #2c3e50;'>
                    <li>You can download individual chapters</li>
                    <li>Or the complete audiobook as MP3</li>
                </ul>
            </li>
        </ol>
    </div>
    """, unsafe_allow_html=True)