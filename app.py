import streamlit as st
import tempfile
import pandas as pd
from datetime import datetime
import os
import requests
import time
import re

st.title("Classroom Speaking Proficiency Test")
st.write("Please complete all parts. Speak clearly and naturally.")

name = st.text_input("Full Name")
institution = st.text_input("Institution")

def transcribe_audio_assemblyai(audio_bytes):
    API_KEY = st.secrets.get("ASSEMBLYAI_API_KEY", "")
    
    if not API_KEY:
        return None, "Error: API key not configured."
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm', mode='wb') as tmp:
        tmp.write(audio_bytes.getvalue())
        tmp_path = tmp.name
    
    try:
        headers = {"authorization": API_KEY}
        
        # Upload audio
        with open(tmp_path, "rb") as f:
            upload_response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                data=f
            )
        
        if upload_response.status_code != 200:
            return None, f"Upload error: {upload_response.text}"
        
        upload_url = upload_response.json().get("upload_url")
        if not upload_url:
            return None, "Error: Failed to get upload URL"
        
        # Request transcription with additional features
        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json={
                "audio_url": upload_url,
                "speech_models": ["universal-2"],  # FIXED: valid model
                "punctuate": True,
                "format_text": True
            },
            headers=headers
        )
        
        if transcript_response.status_code != 200:
            return None, f"Transcription request error: {transcript_response.text}"
        
        transcript_data = transcript_response.json()
        transcript_id = transcript_data.get("id")
        
        if not transcript_id:
            return None, f"Error: No transcript ID received."
        
        # Poll for completion
        max_attempts = 90
        for attempt in range(max_attempts):
            status_response = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers
            )
            
            if status_response.status_code != 200:
                return None, f"Status check error: {status_response.text}"
            
            result = status_response.json()
            status = result.get("status")
            
            if status == "completed":
                return result, None
            elif status == "error":
                error_msg = result.get("error", "Unknown error")
                return None, f"Transcription failed: {error_msg}"
            
            time.sleep(2)
        
        return None, "Error: Transcription timeout"
    
    except Exception as e:
        return None, f"Error: {str(e)}"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def calculate_accuracy_score(transcript, reference):
    """Calculate word accuracy score"""
    transcript_words = set(transcript.lower().split())
    reference_words = set(reference.lower().split())
    
    if not reference_words:
        return 0
    
    matches = len(transcript_words & reference_words)
    accuracy = (matches / len(reference_words)) * 100
    return min(accuracy / 20, 5)  # Convert to 0-5 scale

def calculate_fluency_score(transcript, audio_duration=None):
    """Calculate fluency based on word count and sentence structure"""
    words = transcript.split()
    word_count = len(words)
    
    # Check for complete sentences (ending with . ! ?)
    sentences = re.split(r'[.!?]+', transcript)
    complete_sentences = [s.strip() for s in sentences if s.strip()]
    
    # Base fluency on word count
    fluency = min(word_count / 20, 5)
    
    # Bonus for complete sentences
    if len(complete_sentences) >= 2:
        fluency = min(fluency + 0.5, 5)
    
    return fluency

def calculate_intonation_score(result):
    """Estimate intonation based on punctuation and sentence variety"""
    text = result.get("text", "")
    
    # Count punctuation variety (questions, exclamations, statements)
    has_question = "?" in text
    has_exclamation = "!" in text
    has_period = "." in text
    
    # Check for sentence length variety
    sentences = re.split(r'[.!?]+', text)
    sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
    
    score = 2.5  # Base score
    
    # Add points for variety
    if has_question:
        score += 0.5
    if has_exclamation:
        score += 0.5
    if has_period:
        score += 0.5
    
    # Add points for varied sentence length
    if sentence_lengths and len(set(sentence_lengths)) > 1:
        score += 1.0
    
    return min(score, 5)

st.header("Part 1: Repeat the Sentence")
sentences = [
    "Please open your books to page ten.",
    "Work in pairs and discuss the question.",
    "You have five minutes to complete this task."
]

part1_results = []
for i, sentence in enumerate(sentences):
    st.write(f"**Sentence {i+1}:** {sentence}")
    audio = st.audio_input(f"Record Sentence {i+1}", key=f"p1_{i}")
    if audio:
        with st.spinner("Transcribing and analyzing..."):
            result, error = transcribe_audio_assemblyai(audio)
        
        if error:
            st.error(f"⚠️ {error}")
        elif result:
            transcript = result.get("text", "")
            st.write("**Transcript:**", transcript)
            
            if transcript and transcript != "No speech detected":
                # Calculate scores
                accuracy = calculate_accuracy_score(transcript, sentence)
                fluency = calculate_fluency_score(transcript)
                intonation = calculate_intonation_score(result)
                total = (accuracy + fluency + intonation) / 3
                
                # Display scores
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Accuracy", f"{accuracy:.1f}/5")
                with col2:
                    st.metric("Fluency", f"{fluency:.1f}/5")
                with col3:
                    st.metric("Intonation", f"{intonation:.1f}/5")
                with col4:
                    st.metric("Total", f"{total:.1f}/5")
                
                part1_results.append({
                    "accuracy": accuracy,
                    "fluency": fluency,
                    "intonation": intonation,
                    "total": total
                })
            else:
                st.warning("⚠️ No speech detected. Please try again.")

st.header("Part 2: Respond to Student Questions")
prompts = [
    "When will attendance be uploaded?",
    "Can we submit the assignment late?"
]

part2_results = []
for i, prompt in enumerate(prompts):
    st.write(f"**Student:** {prompt}")
    audio = st.audio_input("Record your response", key=f"p2_{i}")
    if audio:
        with st.spinner("Transcribing and analyzing..."):
            result, error = transcribe_audio_assemblyai(audio)
        
        if error:
            st.error(f"⚠️ {error}")
        elif result:
            transcript = result.get("text", "")
            st.write("**Transcript:**", transcript)
            
            if transcript and transcript != "No speech detected":
                fluency = calculate_fluency_score(transcript)
                intonation = calculate_intonation_score(result)
                total = (fluency + intonation) / 2
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Fluency", f"{fluency:.1f}/5")
                with col2:
                    st.metric("Intonation", f"{intonation:.1f}/5")
                with col3:
                    st.metric("Total", f"{total:.1f}/5")
                
                part2_results.append({
                    "fluency": fluency,
                    "intonation": intonation,
                    "total": total
                })
            else:
                st.warning("⚠️ No speech detected. Please try again.")

st.header("Part 3: Free Explanation")
st.write("Explain how to write a good paragraph.")
audio3 = st.audio_input("Record your explanation", key="p3")
part3_result = None
if audio3:
    with st.spinner("Transcribing and analyzing..."):
        result, error = transcribe_audio_assemblyai(audio3)
    
    if error:
        st.error(f"⚠️ {error}")
    elif result:
        transcript = result.get("text", "")
        st.write("**Transcript:**", transcript)
        
        if transcript and transcript != "No speech detected":
            fluency = calculate_fluency_score(transcript)
            intonation = calculate_intonation_score(result)
            total = (fluency + intonation) / 2
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Fluency", f"{fluency:.1f}/5")
            with col2:
                st.metric("Intonation", f"{intonation:.1f}/5")
            with col3:
                st.metric("Total", f"{total:.1f}/5")
            
            part3_result = {
                "fluency": fluency,
                "intonation": intonation,
                "total": total
            }
        else:
            st.warning("⚠️ No speech detected. Please try again.")

if st.button("Submit Test", type="primary"):
    if not name or not institution:
        st.error("⚠️ Please enter your name and institution before submitting.")
    elif not part1_results and not part2_results and not part3_result:
        st.error("⚠️ Please complete at least one section before submitting.")
    else:
        # Calculate overall scores
        part1_total = sum([r["total"] for r in part1_results])
        part2_total = sum([r["total"] for r in part2_results])
        part3_total = part3_result["total"] if part3_result else 0
        
        grand_total = part1_total + part2_total + part3_total
        max_possible = len(part1_results) * 5 + len(part2_results) * 5 + (5 if part3_result else 0)
        percentage = (grand_total / max_possible * 100) if max_possible > 0 else 0
        
        data = {
            "Name": name,
            "Institution": institution,
            "Part1_Score": round(part1_total, 2),
            "Part2_Score": round(part2_total, 2),
            "Part3_Score": round(part3_total, 2),
            "Total_Score": round(grand_total, 2),
            "Max_Score": max_possible,
            "Percentage": round(percentage, 2),
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        df = pd.DataFrame([data])
        file_exists = os.path.isfile("results.csv")
        df.to_csv("results.csv", mode="a", header=not file_exists, index=False)
        
        st.success(f"✅ Submission recorded successfully!")
        st.balloons()
        
        # Summary
        st.subheader("📊 Test Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Score", f"{grand_total:.1f}/{max_possible}")
        with col2:
            st.metric("Percentage", f"{percentage:.1f}%")
        with col3:
            grade = "A" if percentage >= 90 else "B" if percentage >= 80 else "C" if percentage >= 70 else "D" if percentage >= 60 else "F"
            st.metric("Grade", grade)
