import streamlit as st
import tempfile
import os

st.set_page_config(page_title="Audiobook Generator", page_icon="🎧")

st.title("🎧 PDF to Audiobook Converter")
st.markdown("Transform your PDF books into narrated audiobooks with emotional voices!")

# Sidebar for API key
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("GROQ API Key", type="password")
    if api_key:
        os.environ["GROQ_API_KEY"] = api_key
        st.success("✅ API key saved")
    
    st.markdown("---")
    st.info("""
    **How to use:**
    1. Enter your GROQ API key
    2. Upload a PDF file
    3. Select chapters
    4. Click Generate
    5. Download your audiobook!
    """)

# File upload
uploaded_file = st.file_uploader("Upload PDF Book", type=["pdf"])

if uploaded_file:
    # Save file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        file_path = tmp_file.name
    
    st.success(f"✅ Uploaded: {uploaded_file.name}")
    
    # Simple chapter selection
    st.subheader("📚 Select Chapters")
    
    col1, col2 = st.columns(2)
    with col1:
        process_all = st.checkbox("Process Entire Book")
    
    if not process_all:
        with col2:
            chapter_range = st.slider(
                "Chapters to process",
                1, 100, (1, 10)
            )
    
    # Generate button
    if st.button("🎬 Generate Audiobook", type="primary"):
        if not api_key:
            st.error("Please enter your GROQ API key first!")
        else:
            with st.spinner("Generating audiobook... This may take a few minutes."):
                # Import and use your orchestrator
                try:
                    from orchestrator import ChapterBasedAudiobookAgent
                    
                    agent = ChapterBasedAudiobookAgent(file_path)
                    
                    if process_all:
                        agent.build_all_chapters()
                    else:
                        agent.build_chapter_range(chapter_range[0], chapter_range[1])
                    
                    st.success("✅ Audiobook generated successfully!")
                    
                    # Find the generated file
                    import glob
                    mp3_files = glob.glob("*.mp3")
                    if mp3_files:
                        latest_file = max(mp3_files, key=os.path.getctime)
                        
                        with open(latest_file, "rb") as f:
                            audio_bytes = f.read()
                        
                        st.audio(audio_bytes, format="audio/mp3")
                        
                        st.download_button(
                            label="📥 Download Audiobook",
                            data=audio_bytes,
                            file_name=latest_file,
                            mime="audio/mp3"
                        )
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# Instructions
with st.expander("📋 How to get started"):
    st.markdown("""
    1. **Get a GROQ API key:**
       - Go to [console.groq.com](https://console.groq.com)
       - Sign up for a free account
       - Get your API key from the API Keys section
    
    2. **Upload your PDF:**
       - Make sure it's a text-based PDF (not scanned)
       - The book should have clear chapter headings
    
    3. **Wait for processing:**
       - First time setup may take a few minutes
       - Each chapter takes 1-2 minutes to process
    
    4. **Download your audiobook:**
       - You can download individual chapters
       - Or the complete audiobook as MP3
    """)