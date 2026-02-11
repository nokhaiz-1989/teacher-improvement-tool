import streamlit as st
import tempfile
import whisper
import pandas as pd
from datetime import datetime

st.title("Classroom Speaking Proficiency Test")

st.write("Please complete all parts. Speak clearly and naturally.")

name = st.text_input("Full Name")
institution = st.text_input("Institution")

model = whisper.load_model("base")

def transcribe_audio(audio_file):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name
    result = model.transcribe(tmp_path)
    return result["text"]

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
    audio = st.audio_input(f"Record Sentence {i+1}", key=f"p1_{i}")

    if audio:
        transcript = transcribe_audio(audio)
        st.write("Transcript:", transcript)

        # simple accuracy score
        score = len(set(transcript.lower().split()) &
                    set(sentence.lower().split())) / len(sentence.split()) * 5

        part1_scores.append(score)
        st.write("Accuracy Score:", round(score,2))

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
    audio = st.audio_input("Record your response", key=f"p2_{i}")

    if audio:
        transcript = transcribe_audio(audio)
        st.write("Transcript:", transcript)

        word_count = len(transcript.split())
        fluency_score = min(word_count/20, 5)
        part2_scores.append(fluency_score)

        st.write("Fluency Score:", round(fluency_score,2))

# --------------------
# PART 3
# --------------------
st.header("Part 3: Free Explanation")

st.write("Explain how to write a good paragraph.")

audio3 = st.audio_input("Record your explanation", key="p3")

part3_score = None

if audio3:
    transcript = transcribe_audio(audio3)
    st.write("Transcript:", transcript)

    word_count = len(transcript.split())
    part3_score = min(word_count/40, 5)
    st.write("Fluency Score:", round(part3_score,2))

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
    df.to_csv("results.csv", mode="a", header=False, index=False)

    st.success("Submission recorded successfully.")
