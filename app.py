import streamlit as st
import tempfile
import whisper
import pandas as pd
from datetime import datetime
import os

st.title("Classroom Speaking Proficiency Test")
st.write("Please complete all parts. Speak clearly and naturally.")

name = st.text_input("Full Name")
institution = st.text_input("Institution")

# Load model once
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

model = load_whisper_model()

def transcribe_audio(audio_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name
    try:
        result = model.transcribe(tmp_path)
        return result["text"]
    finally:
        os.unlink(tmp_path)

# --------------------
# PART 1
# --------------------
st.header("Part 1: Repeat the Sentence")
sentences = [
    "Please open your books to page ten.",
    "Work in pairs and discuss the question.",
    "You have five minutes to complete this task."
]

part1_scores = []
for i, sentence in enumerate(sentences):
    st.write(f"Sentence {i+1}: {sentence}")
    audio = st.file_uploader(f"Upload audio for Sentence {i+1}", 
                             type=['wav', 'mp3', 'm4a'], 
                             key=f"p1_{i}")
    if audio:
        transcript = transcribe_audio(audio)
        st.write("Transcript:", transcript)
        # simple accuracy score
        score = len(set(transcript.lower().split()) & 
                    set(sentence.lower().split())) / len(sentence.split()) * 5
        part1_scores.append(score)
        st.write("Accuracy Score:", round(score, 2))

# --------------------
# PART 2
# --------------------
st.header("Part 2: Respond to Student Questions")
prompts = [
    "When will attendance be uploaded?",
    "Can we submit the assignment late?"
]

part2_scores = []
for i, prompt in enumerate(prompts):
    st.write(f"Student: {prompt}")
    audio = st.file_uploader("Upload your response", 
                             type=['wav', 'mp3', 'm4a'], 
                             key=f"p2_{i}")
    if audio:
        transcript = transcribe_audio(audio)
        st.write("Transcript:", transcript)
        word_count = len(transcript.split())
        fluency_score = min(word_count/20, 5)
        part2_scores.append(fluency_score)
        st.write("Fluency Score:", round(fluency_score, 2))

# --------------------
# PART 3
# --------------------
st.header("Part 3: Free Explanation")
st.write("Explain how to write a good paragraph.")
audio3 = st.file_uploader("Upload your explanation", 
                          type=['wav', 'mp3', 'm4a'], 
                          key="p3")
part3_score = None
if audio3:
    transcript = transcribe_audio(audio3)
    st.write("Transcript:", transcript)
    word_count = len(transcript.split())
    part3_score = min(word_count/40, 5)
    st.write("Fluency Score:", round(part3_score, 2))

# --------------------
# SAVE RESULTS
# --------------------
if st.button("Submit Test"):
    total_score = (
        sum(part1_scores) +
        sum(part2_scores) +
        (part3_score if part3_score else 0)
    )
    data = {
        "Name": name,
        "Institution": institution,
        "Score": total_score,
        "Date": datetime.now()
    }
    df = pd.DataFrame([data])
    
    # Check if file exists to write header
    file_exists = os.path.isfile("results.csv")
    df.to_csv("results.csv", mode="a", header=not file_exists, index=False)
    st.success("Submission recorded successfully.")
