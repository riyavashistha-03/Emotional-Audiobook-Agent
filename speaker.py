import os
import soundfile as sf
from kokoro import KPipeline
import numpy as np

class AudiobookSpeaker :
    def __init__(self, lang_code='a'):
        self.pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
        self.voice_dir = os.path.join("model_assets", "voices")
        self.voice_map = {
            "joyful" : "af_bella.pt",
            "somber" : "bm_daniel.pt",
            "tense" :"af_bella.pt",
            "neutral" : "af_bella.pt"
        }

    def generate_audio(self, text, emotional_notes, output_filename) :
        # 1. Determine which voice to use
        emotion = emotional_notes.get("emotion", "neutral")
        voice_file = self.voice_map.get(emotion, "af_bella.pt")
        voice_path = os.path.join(self.voice_dir, voice_file)
        # 2. Get speed/pitch from emotional notes (if provided)
        speed = emotional_notes.get("reading_speed", 1.0)
        
        print(f"🎙️ Speaker: Using {voice_file} for a {emotion} tone...")
        if not os.path.exists(voice_path):
            print(f"warning: Voice ffile {voice_path} not found.")
            voice_path = os.path.join(self.voice_dir, "af_bella.pt")
            
        generator = self.pipeline(
            text, 
            voice=voice_path, 
            speed=speed, 
            split_pattern=r'\n+'
            )
        
        audio_chunks = []
        for i, (gs, ps, audio) in enumerate(generator):
            audio_chunks.append(audio)

        if audio_chunks:
            combined_audio = np.concatenate(audio_chunks)
            sf.write(output_filename, combined_audio, 24000)
            print(f"✅ Audio saved as: {output_filename}")
        else:
            print("❌ Error: No audio was generated.")
    
if __name__ == "__main__":
    # 1. Initialize our production speaker
    my_speaker = AudiobookSpeaker()

    # 2. Mock some emotional notes (as if they came from the Director)
    test_notes = {
        "emotion": "somber",  # This should trigger the Daniel voice
        "reading_speed": 1.0
    }

    test_text = "This is a test of the Daniel voice. If this works, the production speaker is ready."

    # 3. Call the function to generate audio
    print("🚀 Starting the production speaker...")
    my_speaker.generate_audio(test_text, test_notes, "daniel_test_output.wav")   
