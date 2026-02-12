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
    """
    Comprehensive grammar assessment based on:
    1. Sentence structure and completeness
    2. Subject-verb agreement patterns
    3. Proper use of articles, prepositions, and conjunctions
    4. Sentence variety and complexity
    """
    if not transcript or len(transcript.strip()) < 5:
        return 0.5
    
    words = transcript.split()
    text_lower = transcript.lower()
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', transcript)
    complete_sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) >= 3]
    
    if len(complete_sentences) == 0:
        return 1.0
    
    # === 1. SENTENCE STRUCTURE (2.0 points) ===
    structure_score = 0.5  # Base
    
    # Check for proper capitalization
    proper_caps = sum(1 for s in complete_sentences if s and s[0].isupper())
    if proper_caps > 0:
        structure_score += 0.5
    
    # Check for complete sentences (subject + verb patterns)
    sentence_count = len(complete_sentences)
    if sentence_count >= 2:
        structure_score += 0.5
    if sentence_count >= 3:
        structure_score += 0.5
    
    structure_score = min(structure_score, 2.0)
    
    # === 2. VERB USAGE (1.5 points) ===
    verb_score = 0
    
    # Common verbs (present, past, modal)
    common_verbs = ['is', 'are', 'am', 'was', 'were', 'be', 'been', 'being',
                   'have', 'has', 'had', 'do', 'does', 'did',
                   'will', 'would', 'can', 'could', 'should', 'shall', 'may', 'might', 'must']
    
    verb_count = sum(1 for word in text_lower.split() if word in common_verbs)
    
    if verb_count >= 1:
        verb_score += 0.5
    if verb_count >= 2:
        verb_score += 0.5
    if verb_count >= 3:
        verb_score += 0.5
    
    verb_score = min(verb_score, 1.5)
    
    # === 3. ARTICLES, PREPOSITIONS, CONJUNCTIONS (1.0 point) ===
    function_score = 0
    
    articles = ['a', 'an', 'the']
    prepositions = ['in', 'on', 'at', 'to', 'for', 'with', 'by', 'from', 'of', 'about']
    conjunctions = ['and', 'but', 'or', 'so', 'because', 'if', 'when', 'while', 'although']
    
    has_articles = any(article in text_lower.split() for article in articles)
    has_prepositions = any(prep in text_lower.split() for prep in prepositions)
    has_conjunctions = any(conj in text_lower.split() for conj in conjunctions)
    
    if has_articles:
        function_score += 0.3
    if has_prepositions:
        function_score += 0.4
    if has_conjunctions:
        function_score += 0.3
    
    function_score = min(function_score, 1.0)
    
    # === 4. SENTENCE VARIETY & COMPLEXITY (0.5 points) ===
    variety_score = 0
    
    # Check sentence length variety
    sentence_lengths = [len(s.split()) for s in complete_sentences]
    if len(set(sentence_lengths)) > 1:
        variety_score += 0.25
    
    # Check for complex sentences (with subordinate clauses)
    subordinate_markers = ['because', 'since', 'although', 'while', 'if', 'when', 'that', 'which', 'who']
    has_complexity = any(marker in text_lower.split() for marker in subordinate_markers)
    if has_complexity:
        variety_score += 0.25
    
    variety_score = min(variety_score, 0.5)
    
    # === TOTAL GRAMMAR SCORE ===
    total_score = structure_score + verb_score + function_score + variety_score
    
    # Ensure variation between 0.5 and 5.0
    final_score = max(0.5, min(5.0, total_score))
    
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
    "You have five minutes to complete this task.",
    "Did everyone understand the instructions?",
    "First, read the passage carefully, then answer the questions."
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
    "Can we submit the assignment late?",
    "How do you differentiate between formative and summative assessment?"
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
        
        # Display total score
        st.metric("Total Score", f"{total_score:.1f}/{max_score:.0f}")
        
        # Calculate proficiency level
        proficiency_percentage = percentage
        
        if proficiency_percentage >= 90:
            proficiency_level = "Expert"
            color = "#00C851"  # Green
            emoji = "🌟"
        elif proficiency_percentage >= 75:
            proficiency_level = "Advanced"
            color = "#33B5E5"  # Blue
            emoji = "🎯"
        elif proficiency_percentage >= 60:
            proficiency_level = "Intermediate"
            color = "#FFB733"  # Orange
            emoji = "📈"
        elif proficiency_percentage >= 45:
            proficiency_level = "Developing"
            color = "#FF8800"  # Dark Orange
            emoji = "🌱"
        else:
            proficiency_level = "Emerging"
            color = "#FF4444"  # Red
            emoji = "🔰"
        
        # Display proficiency gauge
        st.markdown(f"### {emoji} Speaking Proficiency Level: **{proficiency_level}**")
        
        # Create visual proficiency bar
        st.markdown(f"""
        <div style="background-color: #e0e0e0; border-radius: 10px; padding: 5px; margin: 10px 0;">
            <div style="background-color: {color}; width: {proficiency_percentage}%; height: 30px; border-radius: 8px; 
                        display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
                {proficiency_percentage:.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Proficiency breakdown chart
        st.markdown("#### 📊 Proficiency Breakdown")
        
        # Collect all component scores
        component_scores = {
            "Accuracy": [],
            "Fluency": [],
            "Intonation": [],
            "Vocabulary": [],
            "Grammar": []
        }
        
        # Gather Part 1 scores
        for rec in st.session_state.part1_recordings.values():
            component_scores["Accuracy"].append(rec["accuracy"])
            component_scores["Fluency"].append(rec["fluency"])
            component_scores["Intonation"].append(rec["intonation"])
        
        # Gather Part 2 and Part 3 scores
        for rec in st.session_state.part2_recordings.values():
            component_scores["Vocabulary"].append(rec["vocabulary"])
            component_scores["Grammar"].append(rec["grammar"])
            component_scores["Fluency"].append(rec["fluency"])
            component_scores["Intonation"].append(rec["intonation"])
        
        if st.session_state.part3_recording:
            rec = st.session_state.part3_recording
            component_scores["Vocabulary"].append(rec["vocabulary"])
            component_scores["Grammar"].append(rec["grammar"])
            component_scores["Fluency"].append(rec["fluency"])
            component_scores["Intonation"].append(rec["intonation"])
        
        # Calculate averages
        avg_scores = {}
        for component, scores in component_scores.items():
            if scores:
                avg_scores[component] = sum(scores) / len(scores)
        
        # Display component bars
        for component, avg in avg_scores.items():
            percentage_comp = (avg / 5) * 100
            
            # Color coding based on score
            if avg >= 4.5:
                bar_color = "#00C851"
            elif avg >= 3.5:
                bar_color = "#33B5E5"
            elif avg >= 2.5:
                bar_color = "#FFB733"
            else:
                bar_color = "#FF8800"
            
            st.markdown(f"""
            <div style="margin: 8px 0;">
                <strong>{component}</strong> ({avg:.1f}/5)
                <div style="background-color: #e0e0e0; border-radius: 5px; padding: 2px; margin-top: 3px;">
                    <div style="background-color: {bar_color}; width: {percentage_comp}%; height: 20px; border-radius: 4px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Encouraging remarks and areas for improvement
        st.markdown("---")
        st.markdown("### 💬 Feedback & Areas for Growth")
        
        # Identify strengths and areas for improvement
        strengths = []
        improvements = []
        
        for component, avg in avg_scores.items():
            if avg >= 4.0:
                strengths.append(component)
            elif avg < 3.0:
                improvements.append(component)
        
        # Encouraging message
        if proficiency_percentage >= 90:
            st.success("🌟 **Outstanding performance!** Your speaking proficiency demonstrates excellence across all areas. You're setting a wonderful example for effective classroom communication!")
        elif proficiency_percentage >= 75:
            st.info("🎯 **Great work!** You show strong speaking skills with clear communication. Keep refining your techniques to reach expert level!")
        elif proficiency_percentage >= 60:
            st.info("📈 **Good progress!** You're building solid speaking foundations. With continued practice, you'll see significant improvement!")
        else:
            st.warning("🌱 **Keep growing!** Every expert was once a beginner. Focus on the improvement areas below, and you'll see great progress with consistent practice!")
        
        # Strengths
        if strengths:
            st.markdown(f"**✅ Your Strengths:** {', '.join(strengths)}")
            st.write("These areas showcase your natural abilities. Continue to leverage these skills in your teaching!")
        
        # Areas for improvement with specific tips
        if improvements:
            st.markdown(f"**🎯 Focus Areas for Growth:** {', '.join(improvements)}")
            st.write("**Personalized Tips:**")
            
            for area in improvements:
                if area == "Fluency":
                    st.write("• **Fluency:** Practice speaking at a steady pace (120-160 words/minute). Record yourself and minimize filler words like 'um' and 'uh'.")
                elif area == "Intonation":
                    st.write("• **Intonation:** Vary your pitch and emphasize key words. Try reading stories aloud with emotion to practice natural stress patterns.")
                elif area == "Pronunciation":
                    st.write("• **Pronunciation:** Focus on clear articulation. Practice tongue twisters and record yourself to identify unclear sounds.")
                elif area == "Vocabulary":
                    st.write("• **Vocabulary:** Expand your word choice by reading diverse materials. Try using synonyms when explaining concepts.")
                elif area == "Grammar":
                    st.write("• **Grammar:** Review sentence structure basics. Speak in complete sentences and practice organizing thoughts before speaking.")
                elif area == "Accuracy":
                    st.write("• **Accuracy:** Listen carefully and repeat slowly. Focus on pronouncing each word clearly rather than rushing.")
        
        # General encouragement
        st.markdown("---")
        st.markdown("""
        **Remember:** Effective teaching communication is a skill that improves with practice. Every small improvement 
        makes a difference in how students understand and engage with your lessons. Keep practicing, stay confident, 
        and celebrate your progress! 🎓✨
        """)
        
        # Additional practice resources
        with st.expander("📚 Practice Resources & Tips"):
            st.markdown("""
            **Daily Practice Ideas:**
            - Record 2-minute daily voice notes explaining simple concepts
            - Practice classroom instructions in front of a mirror
            - Join speaking clubs or teacher peer practice groups
            - Listen to educational podcasts and mimic their speaking patterns
            - Use language learning apps focused on pronunciation
            
            **Before Teaching:**
            - Warm up your voice with simple vocal exercises
            - Practice saying new vocabulary words aloud
            - Rehearse key instructions you'll give in class
            - Breathe deeply to reduce anxiety and improve voice quality
            """)

        
        # Save to CSV
        proficiency_level = "Expert" if percentage >= 90 else "Advanced" if percentage >= 75 else "Intermediate" if percentage >= 60 else "Developing" if percentage >= 45 else "Emerging"
        
        data = {
            "Name": name,
            "Institution": institution,
            "Part1_Avg": round(sum(part1_scores) / len(part1_scores), 2) if part1_scores else 0,
            "Part2_Avg": round(sum(part2_scores) / len(part2_scores), 2) if part2_scores else 0,
            "Part3_Score": round(part3_score, 2),
            "Total_Score": round(total_score, 2),
            "Percentage": round(percentage, 2),
            "Proficiency_Level": proficiency_level,
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        df = pd.DataFrame([data])
        file_exists = os.path.isfile("results.csv")
        df.to_csv("results.csv", mode="a", header=not file_exists, index=False)
