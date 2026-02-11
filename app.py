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
    
    # Save the raw audio data directly
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm', mode='wb') as tmp:
        tmp.write(audio_bytes.getvalue())
        tmp_path = tmp.name
    
    try:
        headers = {"authorization": API_KEY}
        
        # Step 1: Upload the audio file directly
        with open(tmp_path, "rb") as f:
            upload_response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                data=f
            )
        
        if upload_response.status_code != 200:
            return f"Upload error: {upload_response.text}"
        
        upload_url = upload_response.json().get("upload_url")
        if not upload_url:
            return "Error: Failed to get upload URL"
        
        # Step 2: Request transcription with CORRECT parameter
        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json={
                "audio_url": upload_url,
                "speech_models": ["nano"]  # FIXED: plural + array
            },
            headers=headers
        )
        
        if transcript_response.status_code != 200:
            return f"Transcription request error: {transcript_response.text}"
        
        transcript_data = transcript_response.json()
        transcript_id = transcript_data.get("id")
        
        if not transcript_id:
            return f"Error: No transcript ID received. Response: {transcript_data}"
        
        # Step 3: Poll for completion
        max_attempts = 90
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
                text = result.get("text", "")
                return text if text else "No speech detected"
            elif status == "error":
                error_msg = result.get("error", "Unknown error")
                return f"Transcription failed: {error_msg}"
            
            time.sleep(2)
        
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
        with st.spinner("Transcribing... (this may take 10-15 seconds)"):
            transcript = transcribe_audio_assemblyai(audio)
        st.write("**Transcript:**", transcript)
        
        if not transcript.startswith("Error") and not transcript.startswith("Transcription failed") and transcript != "No speech detected":
            score = len(set(transcript.lower().split()) & set(sentence.lower().split())) / len(sentence.split()) * 5
            part1_scores.append(score)
            st.write("**Accuracy Score:**", round(score, 2), "/ 5")
        else:
            st.warning("⚠️ Could not transcribe. Please record again and speak clearly.")

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
        
        if not transcript.startswith("Error") and not transcript.startswith("Transcription failed") and transcript != "No speech detected":
            word_count = len(transcript.split())
            fluency_score = min(word_count/20, 5)
            part2_scores.append(fluency_score)
            st.write("**Fluency Score:**", round(fluency_score, 2), "/ 5")
        else:
            st.warning("⚠️ Could not transcribe. Please record again and speak clearly.")

st.header("Part 3: Free Explanation")
st.write("Explain how to write a good paragraph.")
audio3 = st.audio_input("Record your explanation", key="p3")
part3_score = None
if audio3:
    with st.spinner("Transcribing..."):
        transcript = transcribe_audio_assemblyai(audio3)
    st.write("**Transcript:**", transcript)
    
    if not transcript.startswith("Error") and not transcript.startswith("Transcription failed") and transcript != "No speech detected":
        word_count = len(transcript.split())
        part3_score = min(word_count/40, 5)
        st.write("**Fluency Score:**", round(part3_score, 2), "/ 5")
    else:
        st.warning("⚠️ Could not transcribe. Please record again and speak clearly.")

if st.button("Submit Test", type="primary"):
    if not name or not institution:
        st.error("⚠️ Please enter your name and institution before submitting.")
    else:
        total_score = sum(part1_scores) + sum(part2_scores) + (part3_score if part3_score else 0)
        data = {
            "Name": name,
            "Institution": institution,
            "Part1_Score": round(sum(part1_scores), 2),
            "Part2_Score": round(sum(part2_scores), 2),
            "Part3_Score": round(part3_score if part3_score else 0, 2),
            "Total_Score": round(total_score, 2),
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        df = pd.DataFrame([data])
        file_exists = os.path.isfile("results.csv")
        df.to_csv("results.csv", mode="a", header=not file_exists, index=False)
        st.success(f"✅ Submission recorded successfully! Total Score: {round(total_score, 2)}")
        st.balloons()
