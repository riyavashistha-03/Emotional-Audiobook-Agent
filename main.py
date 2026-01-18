import fitz  # PyMuPDF
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class StoryDirector : 
    """The AI Agent that decides the 'voice' and 'emotion' of the text."""

    def analyze_tones(self, text_snippet):
        prompt = f"""
        You are a professional audiobook director. ANalyze the following text sbippet and determine rhw bext voice settings.

        Text: '{text_snippet}'

        Return ONLY a JSON object with these keys:
        - "emotion" : (eg. mysterious, joyful, terrified, neutral)
        -"pitch" : (eg. low, medium, high)
        -"pace" : (eg. slow, nomal, fast)
        -"voice_type" : (eg. deep male, soft female, child-like)
        """
        response = client.chat.completions.create(
            model = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return response.choice[0].message.content
    
    def extract_text_from_pdf(self, pdf_path):
        #Extract text from pdf and breaks it into managable chunks
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        return full_text[:500]

if __name__=="__main__":
    director = StoryDirector()
    path_to_pdf = r"C:\Users\Rahul Dev\OneDrive\Desktop\Projects2026\emotioal-audiobook-agent\How To Win Friends And Influence People - Carnegie, Dale.pdf"

    if os.path.exists(path_to_pdf) :
        print("Extracting text....")
        snippet = extract_text_from_pdf(path_to_pdf)

        print("Director is analyzing the scene...")
        directions = director.analyze_tone(snippet)
        print("\n--Audio production Notes---")
        print(directions)

    else :
        print(f"Error: Please place a file named '{path_to_pdf}' in the folder")
