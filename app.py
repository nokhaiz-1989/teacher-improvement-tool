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
        
        # Request transcription
        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json={
                "audio_url": upload_url,
                "speech_models": ["universal-2"],
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

def display_star_rating(score, label):
    """Display score as stars (out of 5)"""
    filled_stars = int(round(score))
    empty_stars = 5 - filled_stars
    stars = "⭐" * filled_stars + "☆" * empty_stars
    st.write(f"**{label}:** {stars} ({score:.1f}/5)")

def calculate_accuracy_score(transcript, reference):
    """Calculate word accuracy score"""
    transcript_words = set(transcript.lower().split())
    reference_words = set(reference.lower().split())
    
    if not reference_words:
        return 0
    
    matches = len(transcript_words & reference_words)
    accuracy = (matches / len(reference_words)) * 5
    return min(accuracy, 5)

def calculate_fluency_score(transcript, audio_duration=None):
    """
    Calculate fluency based on:
    1. Speaking rate (words per minute)
    2. Pronunciation quality (approximated via word completeness)
    3. Verbal pauses (filler words and hesitations)
    """
    words = transcript.split()
    word_count = len(words)
    
    if word_count == 0:
        return 0.5
    
    # === 1. SPEAKING RATE (Speed) ===
    # Ideal rate: 120-160 words per minute
    # For short responses, we estimate based on word density
    if audio_duration and audio_duration > 0:
        wpm = (word_count / audio_duration) * 60
    else:
        # Estimate: assume 2 seconds per word for short clips
        estimated_duration = word_count * 2
        wpm = (word_count / estimated_duration) * 60
    
    # Score speaking rate
    if 120 <= wpm <= 160:
        rate_score = 2.0  # Optimal rate
    elif 100 <= wpm < 120 or 160 < wpm <= 180:
        rate_score = 1.5  # Acceptable
    elif 80 <= wpm < 100 or 180 < wpm <= 200:
        rate_score = 1.0  # Needs improvement
    else:
        rate_score = 0.5  # Too slow or too fast
    
    # === 2. PRONUNCIATION QUALITY ===
    # Approximate pronunciation by checking for complete, recognizable words
    # Well-pronounced speech typically has words > 2 characters
    well_formed_words = [w for w in words if len(w) > 2 and w.isalpha()]
    pronunciation_ratio = len(well_formed_words) / word_count if word_count > 0 else 0
    
    if pronunciation_ratio >= 0.85:
        pronunciation_score = 2.0
    elif pronunciation_ratio >= 0.70:
        pronunciation_score = 1.5
    elif pronunciation_ratio >= 0.55:
        pronunciation_score = 1.0
    else:
        pronunciation_score = 0.5
    
    # === 3. VERBAL PAUSES (Fillers and Hesitations) ===
    filler_words = ['um', 'uh', 'like', 'you know', 'so', 'actually', 'basically', 
                    'er', 'hmm', 'well', 'kind of', 'sort of']
    
    # Count filler occurrences
    text_lower = transcript.lower()
    filler_count = sum(text_lower.count(filler) for filler in filler_words)
    
    # Calculate filler ratio
    filler_ratio = filler_count / word_count if word_count > 0 else 0
    
    # Score verbal pauses (lower filler ratio = better score)
    if filler_ratio <= 0.05:  # Less than 5% fillers
        pause_score = 1.0
    elif filler_ratio <= 0.10:  # 5-10% fillers
        pause_score = 0.75
    elif filler_ratio <= 0.15:  # 10-15% fillers
        pause_score = 0.5
    else:  # More than 15% fillers
        pause_score = 0.25
    
    # === TOTAL FLUENCY SCORE ===
    total_score = rate_score + pronunciation_score + pause_score
    
    # Ensure score is between 0.5 and 5.0 with variation
    final_score = max(0.5, min(5.0, total_score))
    
    return round(final_score, 1)

def calculate_intonation_score(result):
    """
    Calculate intonation based on:
    1. Pitch variation (estimated from punctuation and sentence structure)
    2. Stress patterns (emphasized words, varied sentence types)
    3. Volume dynamics (approximated from text features)
    
    Excellent score (4.5-5.0): Uses excellent pitch, stress, and volume to convey meaning
    """
    text = result.get("text", "")
    
    if not text or len(text.strip()) < 10:
        return 1.0
    
    # === 1. PITCH VARIATION ===
    # Indicated by questions, exclamations, and varied sentence types
    has_question = "?" in text
    has_exclamation = "!" in text
    has_period = "." in text
    
    question_count = text.count("?")
    exclamation_count = text.count("!")
    
    # Score pitch variation
    pitch_score = 1.0  # Base
    if has_question:
        pitch_score += 0.5
    if has_exclamation:
        pitch_score += 0.4
    if question_count + exclamation_count >= 2:
        pitch_score += 0.3  # Multiple varied sentences
    
    pitch_score = min(pitch_score, 2.0)
    
    # === 2. STRESS PATTERNS ===
    # Estimated from sentence length variety, comma usage, and word emphasis
    sentences = re.split(r'[.!?]+', text)
    sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
    
    has_comma = "," in text
    comma_count = text.count(",")
    
    # Check for length variation (indicates natural stress patterns)
    if len(sentence_lengths) >= 2:
        length_variance = len(set(sentence_lengths)) > 1
    else:
        length_variance = False
    
    stress_score = 1.0  # Base
    
    if has_comma:
        stress_score += 0.3  # Pauses indicate stress
    if comma_count >= 2:
        stress_score += 0.2  # Multiple natural pauses
    if length_variance:
        stress_score += 0.5  # Varied sentence structure
    
    # Check for capitalized words (potential emphasis)
    words = text.split()
    mid_sentence_caps = sum(1 for w in words[1:] if w and w[0].isupper() and w not in ['I'])
    if mid_sentence_caps > 0:
        stress_score += 0.3
    
    stress_score = min(stress_score, 2.0)
    
    # === 3. VOLUME DYNAMICS ===
    # Approximated by exclamations, all caps words, and repetition
    all_caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
    has_repetition = len(words) != len(set(words))
    
    volume_score = 0.5  # Base
    
    if has_exclamation:
        volume_score += 0.3  # Exclamations suggest volume change
    if all_caps_words > 0:
        volume_score += 0.2  # Emphasis
    if has_repetition:
        volume_score += 0.2  # Repetition for emphasis
    
    volume_score = min(volume_score, 1.0)
    
    # === TOTAL INTONATION SCORE ===
    total_score = pitch_score + stress_score + volume_score
    
    # Ensure variation between 1.0 and 5.0
    final_score = max(1.0, min(5.0, total_score))
    
    return round(final_score, 1)

def calculate_vocabulary_score(transcript):
    """Calculate vocabulary richness"""
    words = transcript.lower().split()
    unique_words = set(words)
    
    if len(words) == 0:
        return 0
    
    # Vocabulary diversity ratio
    diversity = len(unique_words) / len(words)
    
    # Advanced word count (words longer than 6 letters)
    advanced_words = [w for w in words if len(w) > 6]
    advanced_ratio = len(advanced_words) / len(words) if words else 0
    
    # Base score on diversity
    base_score = diversity * 3
    
    # Bonus for advanced vocabulary
    bonus = advanced_ratio * 2
    
    final_score = min(base_score + bonus, 5)
    
    # Add variation
    return round(final_score, 1)

def calculate_grammar_score(transcript):
    """Estimate grammar based on sentence structure"""
    # Check for complete sentences
    sentences = re.split(r'[.!?]+', transcript)
    complete_sentences = [s.strip() for s in sentences if s.strip()]
    
    # Check for capital letters at start
    proper_capitalization = sum(1 for s in complete_sentences if s and s[0].isupper())
    
    # Base score
    if len(complete_sentences) == 0:
        return 1.0
    
    score = 2.5
    
    # Reward for complete sentences
    if len(complete_sentences) >= 2:
        score += 1.0
    elif len(complete_sentences) >= 3:
        score += 1.5
    
    # Reward for proper capitalization
    if proper_capitalization > 0:
        score += 0.8
    
    # Check for subject-verb patterns (basic grammar check)
    common_verbs = ['is', 'are', 'was', 'were', 'have', 'has', 'will', 'can', 'should']
    has_verbs = any(verb in transcript.lower().split() for verb in common_verbs)
    if has_verbs:
        score += 0.5
    
    final_score = min(score, 5)
    return round(final_score, 1)

# Initialize session state for storing all recordings
if 'part1_recordings' not in st.session_state:
    st.session_state.part1_recordings = {}
if 'part2_recordings' not in st.session_state:
    st.session_state.part2_recordings = {}
if 'part3_recording' not in st.session_state:
    st.session_state.part3_recording = None

st.header("Part 1: Repeat the Sentence")
st.write("*Rubric: Accuracy, Fluency, Intonation (each out of 5 stars)*")

sentences = [
    "Please open your books to page ten.",
    "Work in pairs and discuss the question.",
    "You have five minutes to complete this task."
]

for i, sentence in enumerate(sentences):
    st.write(f"**Sentence {i+1}:** {sentence}")
    audio = st.audio_input(f"Record Sentence {i+1}", key=f"p1_{i}")
    if audio:
        if f"sentence_{i}" not in st.session_state.part1_recordings or st.session_state.part1_recordings[f"sentence_{i}"]["audio"] != audio:
            with st.spinner("Transcribing and analyzing..."):
                result, error = transcribe_audio_assemblyai(audio)
            
            if error:
                st.error(f"⚠️ {error}")
            elif result:
                transcript = result.get("text", "")
                st.write(f"*Transcript: {transcript}*")
                
                if transcript and transcript != "No speech detected":
                    accuracy = calculate_accuracy_score(transcript, sentence)
                    fluency = calculate_fluency_score(transcript)
                    intonation = calculate_intonation_score(result)
                    
                    st.session_state.part1_recordings[f"sentence_{i}"] = {
                        "audio": audio,
                        "transcript": transcript,
                        "accuracy": accuracy,
                        "fluency": fluency,
                        "intonation": intonation
                    }

st.header("Part 2: Respond to Student Questions")
st.write("*Respond in your own words in 1-2 sentences.*")
st.write("*Rubric: Vocabulary, Grammar, Fluency, Intonation (each out of 5 stars)*")

prompts = [
    "When will attendance be uploaded?",
    "Can we submit the assignment late?"
]

for i, prompt in enumerate(prompts):
    st.write(f"**Student:** {prompt}")
    audio = st.audio_input("Record your response", key=f"p2_{i}")
    if audio:
        if f"prompt_{i}" not in st.session_state.part2_recordings or st.session_state.part2_recordings[f"prompt_{i}"]["audio"] != audio:
            with st.spinner("Transcribing and analyzing..."):
                result, error = transcribe_audio_assemblyai(audio)
            
            if error:
                st.error(f"⚠️ {error}")
            elif result:
                transcript = result.get("text", "")
                st.write(f"*Transcript: {transcript}*")
                
                if transcript and transcript != "No speech detected":
                    vocabulary = calculate_vocabulary_score(transcript)
                    grammar = calculate_grammar_score(transcript)
                    fluency = calculate_fluency_score(transcript)
                    intonation = calculate_intonation_score(result)
                    
                    st.session_state.part2_recordings[f"prompt_{i}"] = {
                        "audio": audio,
                        "transcript": transcript,
                        "vocabulary": vocabulary,
                        "grammar": grammar,
                        "fluency": fluency,
                        "intonation": intonation
                    }

st.header("Part 3: Free Explanation")
st.write("*Rubric: Vocabulary, Grammar, Fluency, Intonation (each out of 5 stars)*")
st.write("Explain how to write a good paragraph.")
audio3 = st.audio_input("Record your explanation", key="p3")
if audio3:
    if st.session_state.part3_recording is None or st.session_state.part3_recording["audio"] != audio3:
        with st.spinner("Transcribing and analyzing..."):
            result, error = transcribe_audio_assemblyai(audio3)
        
        if error:
            st.error(f"⚠️ {error}")
        elif result:
            transcript = result.get("text", "")
            st.write(f"*Transcript: {transcript}*")
            
            if transcript and transcript != "No speech detected":
                vocabulary = calculate_vocabulary_score(transcript)
                grammar = calculate_grammar_score(transcript)
                fluency = calculate_fluency_score(transcript)
                intonation = calculate_intonation_score(result)
                
                st.session_state.part3_recording = {
                    "audio": audio3,
                    "transcript": transcript,
                    "vocabulary": vocabulary,
                    "grammar": grammar,
                    "fluency": fluency,
                    "intonation": intonation
                }

if st.button("Submit Test & View Results", type="primary"):
    if not name or not institution:
        st.error("⚠️ Please enter your name and institution before submitting.")
    elif not st.session_state.part1_recordings and not st.session_state.part2_recordings and not st.session_state.part3_recording:
        st.error("⚠️ Please complete at least one section before submitting.")
    else:
        st.success("✅ Test Submitted Successfully!")
        st.balloons()
        
        # Display Part 1 Results
        if st.session_state.part1_recordings:
            st.subheader("📊 Part 1 Results")
            for i in range(len(sentences)):
                if f"sentence_{i}" in st.session_state.part1_recordings:
                    rec = st.session_state.part1_recordings[f"sentence_{i}"]
                    st.write(f"**Sentence {i+1}:**")
                    display_star_rating(rec["accuracy"], "Accuracy")
                    display_star_rating(rec["fluency"], "Fluency")
                    display_star_rating(rec["intonation"], "Intonation")
                    avg = (rec["accuracy"] + rec["fluency"] + rec["intonation"]) / 3
                    st.write(f"**Average: {avg:.1f}/5**")
                    st.write("---")
        
        # Display Part 2 Results
        if st.session_state.part2_recordings:
            st.subheader("📊 Part 2 Results")
            for i in range(len(prompts)):
                if f"prompt_{i}" in st.session_state.part2_recordings:
                    rec = st.session_state.part2_recordings[f"prompt_{i}"]
                    st.write(f"**Question {i+1}:**")
                    display_star_rating(rec["vocabulary"], "Vocabulary")
                    display_star_rating(rec["grammar"], "Grammar")
                    display_star_rating(rec["fluency"], "Fluency")
                    display_star_rating(rec["intonation"], "Intonation")
                    avg = (rec["vocabulary"] + rec["grammar"] + rec["fluency"] + rec["intonation"]) / 4
                    st.write(f"**Average: {avg:.1f}/5**")
                    st.write("---")
        
        # Display Part 3 Results
        if st.session_state.part3_recording:
            st.subheader("📊 Part 3 Results")
            rec = st.session_state.part3_recording
            display_star_rating(rec["vocabulary"], "Vocabulary")
            display_star_rating(rec["grammar"], "Grammar")
            display_star_rating(rec["fluency"], "Fluency")
            display_star_rating(rec["intonation"], "Intonation")
            avg = (rec["vocabulary"] + rec["grammar"] + rec["fluency"] + rec["intonation"]) / 4
            st.write(f"**Average: {avg:.1f}/5**")
        
        # Calculate overall score
        part1_scores = [
            (rec["accuracy"] + rec["fluency"] + rec["intonation"]) / 3
            for rec in st.session_state.part1_recordings.values()
        ]
        part2_scores = [
            (rec["vocabulary"] + rec["grammar"] + rec["fluency"] + rec["intonation"]) / 4
            for rec in st.session_state.part2_recordings.values()
        ]
        part3_score = (
            (st.session_state.part3_recording["vocabulary"] + 
             st.session_state.part3_recording["grammar"] + 
             st.session_state.part3_recording["fluency"] + 
             st.session_state.part3_recording["intonation"]) / 4
        ) if st.session_state.part3_recording else 0
        
        total_score = sum(part1_scores) + sum(part2_scores) + part3_score
        max_score = len(part1_scores) * 5 + len(part2_scores) * 5 + (5 if part3_score else 0)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        st.subheader("🎯 Final Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Score", f"{total_score:.1f}/{max_score:.0f}")
        with col2:
            st.metric("Percentage", f"{percentage:.1f}%")
        with col3:
            grade = "A" if percentage >= 90 else "B" if percentage >= 80 else "C" if percentage >= 70 else "D" if percentage >= 60 else "F"
            st.metric("Grade", grade)
        
        # Save to CSV
        data = {
            "Name": name,
            "Institution": institution,
            "Part1_Avg": round(sum(part1_scores) / len(part1_scores), 2) if part1_scores else 0,
            "Part2_Avg": round(sum(part2_scores) / len(part2_scores), 2) if part2_scores else 0,
            "Part3_Score": round(part3_score, 2),
            "Total_Score": round(total_score, 2),
            "Percentage": round(percentage, 2),
            "Grade": grade,
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        df = pd.DataFrame([data])
        file_exists = os.path.isfile("results.csv")
        df.to_csv("results.csv", mode="a", header=not file_exists, index=False)
