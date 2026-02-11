import streamlit as st
import tempfile
import pandas as pd
from datetime import datetime
import os
import requests

st.title("Classroom Speaking Proficiency Test")
st.write("Please complete all parts. Speak clearly and naturally.")

name = st.text_input("Full Name")
institution = st.text_input("Institution")

def transcribe_audio_assemblyai(audio_bytes):
    API_KEY = st.secrets.get("ASSEMBLYAI_API_KEY", "")
    
    if not API_KEY:
        return "Error: API key not configured"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
        tmp.write(audio_bytes.getvalue())
        tmp_path = tmp.name
    
    try:
        headers = {"authorization": API_KEY}
        
        with open(tmp_path, "rb") as f:
            response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                files={"file": f}
            )
        upload_url = response.json()["upload_url"]
        
        response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json={"audio_url": upload_url},
            headers=headers
        )
        transcript_id = response.json()["id"]
        
        while True:
            response = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers
            )
            status = response.json()["status"]
            
            if status == "completed":
                return response.json()["text"]
            elif status == "error":
                return "Error transcribing audio"
            
            import time
            time.sleep(1)
    
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
        score = len(set(transcript.lower().split()) & set(sentence.lower().split())) / len(sentence.split()) * 5
        part1_scores.append(score)
        st.write("**Accuracy Score:**", round(score, 2), "/ 5")

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
        word_count = len(transcript.split())
        fluency_score = min(word_count/20, 5)
        part2_scores.append(fluency_score)
        st.write("**Fluency Score:**", round(fluency_score, 2), "/ 5")

st.header("Part 3: Free Explanation")
st.write("Explain how to write a good paragraph.")
audio3 = st.audio_input("Record your explanation", key="p3")
part3_score = None
if audio3:
    with st.spinner("Transcribing..."):
        transcript = transcribe_audio_assemblyai(audio3)
    st.write("**Transcript:**", transcript)
    word_count = len(transcript.split())
    part3_score = min(word_count/40, 5)
    st.write("**Fluency Score:**", round(part3_score, 2), "/ 5")

if st.button("Submit Test", type="primary"):
    if not name or not institution:
        st.error("⚠️ Please enter your name and institution before submitting.")
    else:
        total_score = sum(part1_scores) + sum(part2_scores) + (part3_score if part3_score else 0)
        data = {
            "Name": name,
            "Institution": institution,
            "Total_Score": round(total_score, 2),
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        df = pd.DataFrame([data])
        file_exists = os.path.isfile("results.csv")
        df.to_csv("results.csv", mode="a", header=not file_exists, index=False)
        st.success(f"✅ Submission recorded successfully! Total Score: {round(total_score, 2)}")
        st.balloons()
