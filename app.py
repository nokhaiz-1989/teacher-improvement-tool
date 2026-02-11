import streamlit as st
import tempfile
import pandas as pd
from datetime import datetime
import os
import requests
import time

st.title("Classroom Speaking Proficiency Test")
st.write("Please complete all parts. Speak clearly and naturally.")

name = st.text_input("Full Name")
institution = st.text_input("Institution")

def transcribe_audio_assemblyai(audio_bytes):
    API_KEY = st.secrets.get("ASSEMBLYAI_API_KEY", "")
    
    if not API_KEY:
        return "Error: API key not configured. Please add ASSEMBLYAI_API_KEY to Streamlit secrets."
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
        tmp.write(audio_bytes.getvalue())
        tmp_path = tmp.name
    
    try:
        headers = {"authorization": API_KEY}
        
        # Step 1: Upload the audio file
        with open(tmp_path, "rb") as f:
            upload_response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                files={"file": f}
            )
        
        if upload_response.status_code != 200:
            return f"Upload error: {upload_response.text}"
        
        upload_url = upload_response.json().get("upload_url")
        if not upload_url:
            return "Error: Failed to get upload URL"
        
        # Step 2: Request transcription
        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json={"audio_url": upload_url},
            headers=headers
        )
        
        if transcript_response.status_code != 200:
            return f"Transcription request error: {transcript_response.text}"
        
        transcript_data = transcript_response.json()
        transcript_id = transcript_data.get("id")
        
        if not transcript_id:
            return f"Error: No transcript ID received. Response: {transcript_data}"
        
        # Step 3: Poll for completion
        max_attempts = 60  # Wait up to 60 seconds
        for attempt in range(max_attempts):
            status_response = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers
            )
            
            if status_response.status_code != 200:
                return f"Status check error: {status_response.text}"
            
            result = status_response.json()
            status = result.get("status")
            
            if status == "completed":
                return result.get("text", "No text returned")
            elif status == "error":
                error_msg = result.get("error", "Unknown error")
                return f"Transcription failed: {error_msg}"
            
            time.sleep(1)
        
        return "Error: Transcription timeout"
    
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

st.header("Part 1: Repeat the Sentence")
sentences = [
    "Please open your books to page ten.",
    "Work in pairs and discuss the question.",
    "You have five minutes to complete this task."
]

part1_scores = []
for i, sentence in enumerate(sentences):
    st.write(f"**Sentence {i+1}:** {sentence}")
    audio = st.audio_input(f"Record Sentence {i+1}", key=f"p1_{i}")
    if audio:
        with st.spinner("Transcribing... (this may take 5-10 seconds)"):
            transcript = transcribe_audio_assemblyai(audio)
        st.write("**Transcript:**", transcript)
        
        # Only calculate score if transcription was successful
        if not transcript.startswith("Error"):
            score = len(set(transcript.lower().split()) & set(sentence.lower().split())) / len(sentence.split()) * 5
            part1_scores.append(score)
            st.write("**Accuracy Score:**", round(score, 2), "/ 5")
        else:
            st.error("Transcription failed. Please try again.")

st.header("Part 2: Respond to Student Questions")
prompts = [
    "When will attendance be uploaded?",
    "Can we submit the assignment late?"
]

part2_scores = []
for i, prompt in enumerate(prompts):
    st.write(f"**Student:** {prompt}")
    audio = st.audio_input("Record your response", key=f"p2_{i}")
    if audio:
        with st.spinner("Transcribing..."):
            transcript = transcribe_audio_assemblyai(audio)
        st.write("**Transcript:**", transcript)
        
        if not transcript.startswith("Error"):
            word_count = len(transcript.split())
            fluency_score = min(word_count/20, 5)
            part2_scores.append(fluency_score)
            st.write("**Fluency Score:**", round(fluency_score, 2), "/ 5")
        else:
            st.error("Transcription failed. Please try again.")

st.header("Part 3: Free Explanation")
st.write("Explain how to write a good paragraph.")
audio3 = st.audio_input("Record your explanation", key="p3")
part3_score = None
if audio3:
