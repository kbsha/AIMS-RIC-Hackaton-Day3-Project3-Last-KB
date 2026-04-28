"""
FLUX App — Modern, Interactive Tutor for Kids
Real voice interaction, sound effects, drag-and-drop, and sophisticated UI animations.
"""

import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
from core import (
    CurriculumLoader, ChildASRAdapter, ResponseScorer, LearnerState,
    LocalProgressStore, FeedbackGenerator,
)
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
import tempfile
import os
import re
import random
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components

# Page config
st.set_page_config(
    page_title="FLUX Tutor — Interactive Learning for Kids",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern, kid-friendly design (Brilliant.org inspired)
custom_css = """
<style>
* {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
}

:root {
    --primary: #6366F1;
    --primary-light: #818CF8;
    --secondary: #06B6D4;
    --accent: #F59E0B;
    --success: #10B981;
    --danger: #EF4444;
    --purple: #A78BFA;
    --pink: #EC4899;
    --cyan: #22D3EE;
    --bg-light: #F0F9FF;
    --border-radius: 20px;
}

body {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

.stApp {
    background: linear-gradient(180deg, #F0F9FF 0%, #E0F2FE 50%, #F3E8FF 100%);
    overflow-x: hidden;
}

/* Card styling */
.card {
    background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%);
    border-radius: var(--border-radius);
    padding: 24px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07), 0 10px 30px rgba(99, 102, 241, 0.1);
    border: 2px solid #E0E7FF;
    transition: all 0.4s cubic-bezier(0.23, 1, 0.320, 1);
}

.card:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 0 20px 50px rgba(99, 102, 241, 0.25);
    border-color: #C7D2FE;
}

/* Button styling */
.btn-primary {
    background: linear-gradient(135deg, #6366F1 0%, #A78BFA 100%);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: var(--border-radius);
    font-weight: 600;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.35s cubic-bezier(0.23, 1, 0.320, 1);
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4);
}

.btn-primary:hover {
    transform: translateY(-3px) scale(1.05);
    box-shadow: 0 12px 35px rgba(99, 102, 241, 0.6);
}

.btn-primary:active {
    transform: scale(0.96) translateY(-1px);
}

/* Badge styling */
.badge {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 25px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: linear-gradient(135deg, #6366F1 0%, #A78BFA 100%);
    color: white;
    margin: 4px 2px;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    transition: all 0.3s ease;
}

.badge:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.5);
}

/* Title styling with gradient */
h1, h2, h3 {
    background: linear-gradient(135deg, #6366F1 0%, #A78BFA 50%, #EC4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin-bottom: 8px;
}

h1 {
    font-size: 48px;
    animation: fadeInDown 0.8s ease-out;
}

h2 {
    font-size: 36px;
}

/* Animated gradient text */
.gradient-text {
    background: linear-gradient(90deg, #6366F1, #A78BFA, #EC4899, #F59E0B, #10B981, #06B6D4, #6366F1);
    background-size: 300% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: gradientShift 8s ease infinite;
    font-weight: 700;
}

/* Progress bar - enhanced */
.progress-bar {
    height: 14px;
    border-radius: 12px;
    background: linear-gradient(90deg, #E5E7EB 0%, #E5E7EB 100%);
    overflow: hidden;
    margin: 12px 0;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #6366F1 0%, #A78BFA 50%, #EC4899 100%);
    border-radius: 12px;
    transition: width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
    box-shadow: 0 0 15px rgba(99, 102, 241, 0.5);
}

/* Score badge */
.score-badge {
    background: linear-gradient(135deg, #10B981 0%, #06B6D4 100%);
    color: white;
    padding: 20px 30px;
    border-radius: 20px;
    font-size: 28px;
    font-weight: 800;
    text-align: center;
    box-shadow: 0 8px 30px rgba(16, 185, 129, 0.4);
    transition: all 0.4s cubic-bezier(0.23, 1, 0.320, 1);
}

.score-badge:hover {
    transform: scale(1.1) rotate(3deg);
    box-shadow: 0 15px 40px rgba(16, 185, 129, 0.6);
}

/* Animation keyframes */
@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-15px); }
}

@keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.7); }
    50% { opacity: 0.8; }
    100% { box-shadow: 0 0 0 10px rgba(99, 102, 241, 0); }
}

@keyframes fadeInDown {
    from {
        opacity: 0;
        transform: translateY(-30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes gradientShift {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

.bounce { animation: bounce 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite; }
.pulse { animation: pulse 2s ease-in-out infinite; }
.float { animation: float 3s ease-in-out infinite; }
.fade-in { animation: fadeIn 0.6s ease-out; }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

# Initialize session state
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
    st.session_state.score = 0
    st.session_state.responses = []
    st.session_state.mode = 'game'
    st.session_state.voice_enabled = True
    st.session_state.streak = 0

@st.cache_resource
def get_resources():
    loader = CurriculumLoader()
    asr = ChildASRAdapter()
    store = LocalProgressStore()
    return loader, asr, store

loader, asr, store = get_resources()

# ====== HELPER FUNCTIONS ======

def generate_visual(item, width=600, height=360):
    """Generate visual representation of a count."""
    count = item.get('answer_int', 1)
    
    img = Image.new('RGBA', (width, height), (255, 250, 240))
    draw = ImageDraw.Draw(img)
    
    # Draw colorful shapes
    radius = max(18, min(40, width // 20))
    padding = max(10, width // 40)
    cols = max(1, width // (radius * 2 + padding))
    
    colors = ['#FF6347', '#FFD700', '#66CDAA', '#87CEFA', '#DDA0DD', '#FFA07A', '#98FB98']
    
    for i in range(count):
        col = colors[i % len(colors)]
        cx = padding + (i % cols) * (2 * radius + padding) + radius
        cy = 60 + (i // cols) * (2 * radius + padding) + radius
        col_hex = tuple(int(col.lstrip('#')[j:j+2], 16) for j in (0, 2, 4))
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=col_hex)
    
    # Add text
    try:
        f = ImageFont.truetype("arial.ttf", max(16, width // 20))
    except:
        f = ImageFont.load_default()
    
    draw.text((20, height - 50), item.get('stem_en', 'Count'), fill=(60, 60, 60), font=f)
    
    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(tf.name)
    return tf.name

def speak_text(text, lang='en'):
    """Generate and play audio from text using gTTS."""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts.save(tf.name)
        return tf.name
    except Exception as e:
        st.warning(f"Voice not available: {e}")
        return None

def play_sound_effect(success=True):
    """Return audio for sound effect (for Streamlit audio player)."""
    import io
    from scipy.io import wavfile
    
    sr = 22050
    if success:
        # Success: ascending tone
        freq = np.array([440, 554.37, 659.25]) 
        t_segment = np.linspace(0, 0.2, sr // 5)
        sound = np.concatenate([np.sin(2 * np.pi * f * t_segment) * 0.3 for f in freq])
    else:
        # Failure: descending tone
        freq = np.array([440, 349.23, 261.63])
        t_segment = np.linspace(0, 0.2, sr // 5)
        sound = np.concatenate([np.sin(2 * np.pi * f * t_segment) * 0.3 for f in freq])
    
    sound = np.int16(sound * 32767)
    buf = io.BytesIO()
    wavfile.write(buf, sr, sound)
    buf.seek(0)
    return buf.getvalue()

# ====== GAME PAGE ======

def page_game():
    st.markdown("## 🎮 Interactive Game Mode")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        learner_id = st.text_input("👤 Learner ID", value="learner_001")
        learner_name = st.text_input("📝 Name", value="Alex")
        skill = st.selectbox("🎯 Skill", list(loader.by_skill.keys()) or ["counting"])
    
    with col2:
        st.metric("🏆 Score", st.session_state.score)
        st.metric("🔥 Streak", st.session_state.streak)
    
    with col3:
        st.metric("📊 Progress", f"{st.session_state.current_index}/{len(loader.by_skill.get(skill, []))}")
        voice_enabled = st.checkbox("🎤 Voice", value=True)
    
    items = loader.by_skill.get(skill, [])
    
    if not items:
        st.warning("No items found for this skill.")
        return
    
    if st.session_state.current_index >= len(items):
        st.session_state.current_index = 0
    
    item = items[st.session_state.current_index]
    
    # Main game area
    st.markdown("---")
    
    col_main, col_side = st.columns([3, 1])
    
    with col_main:
        st.markdown(f"### 🎯 Question: {item.get('stem_en')}")
        
        # Display visual
        img_path = generate_visual(item, width=800, height=480)
        st.image(img_path, width=800)
        
        # Voice prompt
        if voice_enabled:
            audio_file = speak_text(f"How many? {item.get('stem_en')}")
            if audio_file:
                st.audio(audio_file, autoplay=True)
        
        st.markdown("---")
        st.markdown("#### 👇 Select Your Answer:")
        
        correct = item.get('answer_int', 1)
        opts = sorted(list(set([correct, max(1, correct - 1), correct + 1, correct + 2])))
        
        cols = st.columns(len(opts))
        for i, opt in enumerate(opts):
            with cols[i]:
                if st.button(f"**{opt}** 👆", key=f"ans_{item.get('id')}_{opt}", use_container_width=True):
                    if opt == correct:
                        st.session_state.score += 1
                        st.session_state.streak += 1
                        st.success(f"🎉 Correct! Great job!")
                        
                        # Sound effect
                        audio_buf = play_sound_effect(success=True)
                        st.audio(audio_buf, format='audio/wav')
                        
                        # Voice feedback
                        if voice_enabled:
                            audio_file = speak_text("Excellent! You counted correctly!")
                            if audio_file:
                                st.audio(audio_file)
                        
                        store.add_response(learner_id, skill, item.get('id'), True, 'game_mode')
                        
                        st.balloons()
                        st.session_state.current_index += 1
                    else:
                        st.session_state.streak = 0
                        st.error(f"❌ Not quite. The answer is {correct}.")
                        
                        # Sound effect
                        audio_buf = play_sound_effect(success=False)
                        st.audio(audio_buf, format='audio/wav')
                        
                        # Voice feedback
                        if voice_enabled:
                            audio_file = speak_text(f"The answer is {correct}. Try again!")
                            if audio_file:
                                st.audio(audio_file)
                        
                        store.add_response(learner_id, skill, item.get('id'), False, 'game_mode')
    
    with col_side:
        st.markdown("### 📋 Info")
        st.write(f"**Learner:** {learner_name}")
        st.write(f"**Skill:** {skill}")
        stats = store.get_stats(learner_id)
        if stats:
            st.json({s: f"{v['accuracy']:.1%}" for s, v in stats.items()})

# ====== VOICE MODE PAGE ======

def page_voice():
    st.markdown("## 🎤 Voice Interactive Mode")
    st.write("Speak your answer! The system will listen and respond.")
    
    learner_id = st.text_input("Learner ID (Voice)", value="learner_voice")
    learner_name = st.text_input("Name (Voice)", value="Sam")
    skill = st.selectbox("Skill (Voice)", list(loader.by_skill.keys()) or ["counting"])
    
    items = loader.by_skill.get(skill, [])
    if not items:
        st.warning("No items for this skill.")
        return
    
    item = items[st.session_state.current_index % len(items)]
    
    st.markdown("---")
    st.markdown(f"### 🎯 {item.get('stem_en')}")
    
    # Visual
    img_path = generate_visual(item)
    st.image(img_path, width=500)
    
    # Voice prompt
    audio_file = speak_text(f"Listen carefully. {item.get('stem_en')} How many do you see?")
    if audio_file:
        st.audio(audio_file, autoplay=True)
    
    st.markdown("---")
    
    # WebRTC for voice input
    rtc_config = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
    
    webrtc_ctx = webrtc_streamer(
        key="voice-mode",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=rtc_config,
        media_stream_constraints={"audio": True, "video": False},
        async_processing=True,
    )
    
    if webrtc_ctx.audio_processor:
        try:
            audio_frames = webrtc_ctx.audio_processor.get_frames(timeout=1)
        except Exception:
            audio_frames = None
        
        if audio_frames:
            for frame in audio_frames:
                try:
                    # Process audio
                    sound = frame.to_ndarray()
                    
                    # Save to temp file
                    import soundfile as sf
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                    sf.write(tf.name, sound.T, frame.sample_rate)
                    
                    # Transcribe
                    transcript = asr.transcribe(tf.name)
                    
                    if transcript:
                        st.write(f"**You said:** {transcript}")
                        
                        # Score
                        correct = ResponseScorer.score_response(item.get('answer_int'), transcript, item)
                        
                        if correct:
                            st.success("✅ Correct!")
                            st.session_state.score += 1
                            audio_buf = play_sound_effect(success=True)
                            st.audio(audio_buf, format='audio/wav')
                            store.add_response(learner_id, skill, item.get('id'), True, 'voice_mode')
                        else:
                            st.error(f"❌ The answer is {item.get('answer_int')}")
                            audio_buf = play_sound_effect(success=False)
                            st.audio(audio_buf, format='audio/wav')
                            store.add_response(learner_id, skill, item.get('id'), False, 'voice_mode')
                except Exception as e:
                    st.warning(f"Error: {e}")

# ====== DRAG & DROP PAGE ======

def page_drag_drop():
    st.markdown("## 🎨 Drag & Drop Interactive")
    
    learner_id = st.text_input("Learner ID (Drag)", value="learner_drag")
    skill = st.selectbox("Skill (Drag)", list(loader.by_skill.keys()) or ["counting"])
    
    items = loader.by_skill.get(skill, [])
    if not items:
        st.warning("No items.")
        return
    
    item = items[st.session_state.current_index % len(items)]
    count = item.get('answer_int', 1)
    
    # Advanced drag-drop HTML with enhanced animations
    html_content = f"""
    <style>
    .drag-container {{
        display: flex; gap: 30px; padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px; color: white; font-family: 'Segoe UI', sans-serif;
    }}
    .scene {{
        flex: 1; background: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }}
    .scene h2 {{ margin: 0; color: #667eea; }}
    .dots {{
        display: flex; flex-wrap: wrap; gap: 15px; padding: 20px;
        background: #f0f0f0; border-radius: 10px; margin-top: 15px;
    }}
    .dot {{
        width: 70px; height: 70px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 32px; font-weight: bold; color: white;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        animation: bounce 2s ease-in-out infinite;
    }}
    @keyframes bounce {{
        0%, 100% {{ transform: translateY(0); }}
        50% {{ transform: translateY(-10px); }}
    }}
    .controls {{
        flex: 1; background: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }}
    .tiles {{
        display: flex; flex-wrap: wrap; gap: 10px;
    }}
    .tile {{
        width: 60px; height: 60px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; border: none; border-radius: 10px; cursor: grab;
        font-size: 20px; font-weight: bold; user-select: none;
        transition: all 0.2s ease;
    }}
    .tile:hover {{
        transform: scale(1.1);
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
    }}
    .tile:active {{
        cursor: grabbing;
        transform: scale(0.95);
    }}
    .dropzone {{
        margin-top: 20px; padding: 30px; border: 3px dashed #667eea;
        border-radius: 10px; text-align: center; min-height: 100px;
        background: #f9f9f9; transition: all 0.3s ease;
    }}
    .dropzone.drag-over {{
        background: #e8e8ff; border-color: #764ba2; transform: scale(1.02);
    }}
    .msg {{
        margin-top: 15px; font-weight: bold; font-size: 18px;
        animation: fadeIn 0.5s ease-out;
    }}
    @keyframes fadeIn {{
        0% {{ opacity: 0; }}
        100% {{ opacity: 1; }}
    }}
    #confetti {{
        position: fixed; left: 0; top: 0; z-index: 9999;
        pointer-events: none; width: 100%; height: 100%;
    }}
    </style>

    <canvas id="confetti"></canvas>
    <div class="drag-container">
      <div class="scene">
        <h2>{item.get('stem_en')}</h2>
        <p>Count the objects:</p>
        <div class="dots" id="dots"></div>
      </div>
      <div class="controls">
        <h3 style="margin-top: 0;">Select the number:</h3>
        <div class="tiles" id="tiles"></div>
        <div class="dropzone" id="dropzone">
          <p style="margin: 0; color: #999;">Drop your answer here</p>
        </div>
        <div class="msg" id="msg"></div>
      </div>
    </div>

    <script>
    // Confetti effect
    const canvas = document.getElementById('confetti');
    const ctx = canvas.getContext('2d');
    function resizeCanvas() {{
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }}
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    function confetti() {{
        const particles = [];
        const colors = ['#FF6347', '#FFD700', '#66CDAA', '#87CEFA', '#DDA0DD'];
        for(let i=0; i<100; i++) {{
            particles.push({{
                x: Math.random() * canvas.width,
                y: -20 - Math.random() * 100,
                vx: (Math.random() - 0.5) * 8,
                vy: 3 + Math.random() * 7,
                r: 5 + Math.random() * 8,
                c: colors[Math.floor(Math.random() * colors.length)],
                rot: Math.random() * 360
            }});
        }}
        const anim = setInterval(() => {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            for(let p of particles) {{
                p.x += p.vx;
                p.y += p.vy;
                p.vy += 0.15;
                p.rot += p.vx * 0.5;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot * Math.PI / 180);
                ctx.fillStyle = p.c;
                ctx.fillRect(-p.r/2, -p.r/2, p.r, p.r);
                ctx.restore();
            }}
            if(particles.some(p => p.y < canvas.height)) {{
                particles = particles.filter(p => p.y < canvas.height);
            }} else {{
                clearInterval(anim);
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }}
        }}, 1000/60);
    }}

    // Generate dots
    const colors = ['#FF6347', '#FFD700', '#66CDAA', '#87CEFA', '#DDA0DD', '#FFA07A'];
    const count = {count};
    const dots = document.getElementById('dots');
    for(let i=0; i<count; i++) {{
        const d = document.createElement('div');
        d.className = 'dot';
        d.style.background = colors[i % colors.length];
        d.innerText = '';
        dots.appendChild(d);
    }}

    // Generate tiles (1-9)
    const tiles = document.getElementById('tiles');
    for(let n=1; n<=9; n++) {{
        const t = document.createElement('div');
        t.className = 'tile';
        t.innerText = n;
        t.draggable = true;
        t.dataset.val = n;
        t.addEventListener('dragstart', e => e.dataTransfer.setData('text', n));
        t.addEventListener('click', () => handleDrop(n));
        tiles.appendChild(t);
    }}

    // Drop zone events
    const drop = document.getElementById('dropzone');
    drop.addEventListener('dragover', e => {{
        e.preventDefault();
        drop.classList.add('drag-over');
    }});
    drop.addEventListener('dragleave', () => drop.classList.remove('drag-over'));
    drop.addEventListener('drop', e => {{
        e.preventDefault();
        drop.classList.remove('drag-over');
        const val = parseInt(e.dataTransfer.getData('text'));
        handleDrop(val);
    }});

    function handleDrop(val) {{
        const msg = document.getElementById('msg');
        if(val === count) {{
            msg.innerText = '🎉 Correct!';
            msg.style.color = '#28a745';
            confetti();
        }} else {{
            msg.innerText = `Try again! The answer is ${{count}}.`;
            msg.style.color = '#dc3545';
            drop.animate([
                {{transform: 'translateX(-10px)'}},
                {{transform: 'translateX(10px)'}},
                {{transform: 'translateX(0)'}}
            ], {{duration: 300}});
        }}
    }}
    </script>
    """
    
    st.markdown("---")
    components.html(html_content, height=600)
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Correct"):
            st.session_state.score += 1
            st.success("Response logged!")
            store.add_response(learner_id, skill, item.get('id'), True, 'drag_mode')
    with col2:
        if st.button("❌ Incorrect"):
            st.info("Response logged.")
            store.add_response(learner_id, skill, item.get('id'), False, 'drag_mode')

# ====== DASHBOARD PAGE ======

def page_dashboard():
    st.markdown("## 📊 Progress Dashboard")
    
    learner_id = st.text_input("View progress for:", value="learner_001")
    
    stats = store.get_stats(learner_id)
    
    if not stats:
        st.info("No activity yet.")
        return
    
    col1, col2, col3 = st.columns(3)
    
    df = pd.DataFrame.from_dict(stats, orient='index')
    
    with col1:
        total_attempts = int(df['attempts'].sum())
        st.metric("📊 Total Attempts", total_attempts)
    
    with col2:
        total_correct = int(df['correct'].sum())
        st.metric("✅ Correct", total_correct)
    
    with col3:
        accuracy = (total_correct / total_attempts * 100) if total_attempts > 0 else 0
        st.metric("📈 Accuracy", f"{accuracy:.1f}%")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Accuracy by Skill")
        accuracy_data = df['accuracy'].sort_values(ascending=False)
        st.bar_chart(accuracy_data)
    
    with col2:
        st.subheader("Attempts by Skill")
        attempts_data = df['attempts'].sort_values(ascending=False)
        st.bar_chart(attempts_data)
    
    st.markdown("---")
    st.subheader("Detailed Stats")
    st.dataframe(df, use_container_width=True)

# ====== MAIN ======

def main():
    # Title
    st.markdown("<h1 style='text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 3em;'>🎮 FLUX Tutor</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666; font-size: 18px;'>Modern Interactive Learning for Kids</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Navigation
    mode = st.radio(
        "🎯 Choose Mode:",
        ["🎮 Game", "🎤 Voice", "🎨 Drag & Drop", "📊 Dashboard"],
        horizontal=True,
    )
    
    st.markdown("---")
    
    if mode == "🎮 Game":
        page_game()
    elif mode == "🎤 Voice":
        page_voice()
    elif mode == "🎨 Drag & Drop":
        page_drag_drop()
    elif mode == "📊 Dashboard":
        page_dashboard()

if __name__ == "__main__":
    main()
