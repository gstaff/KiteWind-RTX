# pip install gradio_client
# from gradio_client import Client

# client = Client("abidlabs/whisper")
# client.predict("audio_sample.wav")



# from huggingface_hub import InferenceClient
#
# client = InferenceClient("http://127.0.0.1:8080")
# for token in client.text_generation("How do you make cheese?", max_new_tokens=12, stream=True):
#     print(token)
import os
import requests
def query(payload: dict):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()


HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise Exception("HF_TOKEN environment variable is required to call remote API.")

API_URL = "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}


params = {"max_new_tokens": 512, "stream": True}
output = query({"inputs": prompt, "parameters": params})