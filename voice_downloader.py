import os
import requests

# Ensure folder exists
os.makedirs("model_assets/voices", exist_ok=True)

# Direct URL to the raw binary file on Hugging Face
url = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/bm_daniel.pt"
dest = "model_assets/voices/bm_daniel.pt"

print("📥 Downloading fresh voice pack...")
response = requests.get(url, stream=True)

if response.status_code == 200:
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"✅ Download complete! File size: {os.path.getsize(dest) / 1024:.2f} KB")
else:
    print(f"❌ Download failed. Status code: {response.status_code}")




    #https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/bm_daniel.pt