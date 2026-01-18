import os
import json
import fitz
from pydub import AudioSegment
from main import StoryDirector
from speaker import AudiobookSpeaker

class AudiobookAgent:
    def __init__(self, pdf_path):
        doc = fitz.open(pdf_path)
        print(f"Starting Processing: {len(doc)} pages found.")
        
        master_audio = AudioSegment.empty()
        
        for page_num in range(len(doc)):
            print(f"\n Processing Page {page_num + 1}")
            text = doc[page_num].get_text().strip()
            if not text:
                continue
            
            directions_raw = self.director.analyze_tone(text[:1000]) # Sample for context
            directions = json.loads(directions_raw)
            
            temp_file = os.path.join(self.output_folder, f"page_{page_num}.wav")
            self.speaker.generate_audio(text, directions, temp_file)
            
            page_audio = AudioSegment.from_wav(temp_file)
            master_audio += page_audio
            
            print(r"\n🎬 Exporting final audiobook...")
            master_audio.export("final_audiobook.mp3", format="mp3")
            print("✅ Success! 'final_audiobook.mp3' is ready.")

if __name__ == "__main__":
    agent = AudiobookAgent()
    agent.build_audiobook("How To Win Friends And Influence People - Carnegie, Dale.pdf")
    