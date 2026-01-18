import fitz  # PyMuPDF
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("jsdcb"))

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
            model = "gpt-4o",
            messages = [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return response.choice[0].message.content
    