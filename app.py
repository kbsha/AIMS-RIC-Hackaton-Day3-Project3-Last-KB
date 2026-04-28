import streamlit as st
from core import (
    CurriculumLoader,
    ChildASRAdapter,
    ResponseScorer,
    LearnerState,
    LocalProgressStore,
    FeedbackGenerator,
)
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
import tempfile
import os
import re
import random
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import soundfile as sf
import numpy as np
import time
import streamlit.components.v1 as components


st.set_page_config(page_title="AIMS Tutor Demo", layout="wide")


def generate_visual(item, width=600, height=360):
    visual = item.get('visual', '') or ''
    # extract number from visual string
    m = re.search(r"(\d+)$", visual)
    count = int(m.group(1)) if m else item.get('answer_int', 1)

    img = Image.new('RGBA', (width, height), (255, 250, 240))
    draw = ImageDraw.Draw(img)

    # Draw playful circles for count (wrap to rows)
    radius = max(18, min(40, width // 20))
    padding = max(10, width // 40)
    cols = max(1, width // (radius * 2 + padding))
    x0 = padding
    y0 = 40

    colors = [(255, 99, 71), (255, 215, 0), (102, 205, 170), (135, 206, 250), (221,160,221)]

    for i in range(count):
        col = colors[i % len(colors)]
        cx = x0 + (i % cols) * (2 * radius + padding) + radius
        cy = y0 + (i // cols) * (2 * radius + padding) + radius
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=col)

    # Large friendly text
    try:
        f = ImageFont.truetype("arial.ttf", max(16, width // 20))
    except Exception:
        f = ImageFont.load_default()

    draw.text((width - int(width * 0.25), 10), f"{item.get('id')}", fill=(80, 80, 80), font=f)
    draw.text((20, height - 50), f"{item.get('stem_en')}", fill=(60, 60, 60), font=f)

    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(tf.name)
    return tf.name


@st.cache_resource
def get_resources():
    loader = CurriculumLoader()
    asr = ChildASRAdapter()
    store = LocalProgressStore()
    return loader, asr, store


loader, asr, store = get_resources()


st.title("🎈 AIMS Tutor — Playful Practice for Kids")
st.write("An interactive, kid-friendly tutoring demo with images and sound.")


with st.sidebar:
    st.header("Learner")
    learner_id = st.text_input("Learner ID", value="learner_001")
    learner_name = st.text_input("Name", value="Alex")
    skill_options = list(loader.by_skill.keys()) or ["counting"]
    selected_skill = st.selectbox("Skill", skill_options)
    st.markdown("---")
    page = st.selectbox("Page", ["Play", "Full Puzzle", "Interactive Puzzle", "Dashboard", "Reports", "Settings", "Search"])
    voice_assistant = st.checkbox("Enable Voice Assistant (auto speak)", value=True, key='voice_assistant')
    auto_speak = st.checkbox("Auto-speak prompts", value=True, key='auto_speak')
    st.checkbox("Play mode (one item at a time)", value=True, key='play_mode')


if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
    st.session_state.score = 0


learner = LearnerState(learner_id)
store.add_learner(learner_id, learner_name)

# Welcome audio once per session when voice assistant enabled
if voice_assistant and not st.session_state.get('welcomed'):
    try:
        welcome_text = f"Welcome {learner_name}! Let's play and learn together."
        t = gTTS(text=welcome_text, lang='en')
        tfw = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        t.save(tfw.name)
        st.audio(tfw.name)
    except Exception:
        pass
    st.session_state['welcomed'] = True


items = loader.by_skill.get(selected_skill, [])

if page == "Dashboard":
    st.header("Dashboard — Learner Progress")
    stats = store.get_stats(learner_id)
    if stats:
        import pandas as pd
        df = pd.DataFrame.from_dict(stats, orient='index')
        df = df.reset_index().rename(columns={'index': 'skill'})
        st.dataframe(df)
        if 'accuracy' in df.columns:
            st.subheader("Accuracy by skill")
            st.bar_chart(df.set_index('skill')['accuracy'])
        if 'attempts' in df.columns:
            st.subheader("Attempts by skill")
            st.bar_chart(df.set_index('skill')['attempts'])
    else:
        st.info("No activity yet for this learner.")

elif page == "Reports":
    st.header("Reports")
    st.write("Export learner responses as CSV or view a leaderboard.")
    import sqlite3, pandas as pd, io

    conn = sqlite3.connect(store.db_path)
    try:
        df = pd.read_sql_query(
            "SELECT response_id, learner_id, skill, item_id, correct, transcript, timestamp FROM responses WHERE learner_id = ?",
            conn, params=(learner_id,)
        )
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        st.info("No responses logged yet.")
    else:
        st.dataframe(df)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", data=csv, file_name=f"responses_{learner_id}.csv", mime='text/csv')
        # simple leaderboard across learners
        conn2 = sqlite3.connect(store.db_path)
        try:
            lb = pd.read_sql_query(
                "SELECT learner_id, SUM(correct) as correct_sum, COUNT(*) as attempts FROM responses GROUP BY learner_id ORDER BY correct_sum DESC LIMIT 10",
                conn2
            )
            if not lb.empty:
                st.subheader("Top learners")
                st.table(lb)
        finally:
            conn2.close()

elif page == "Settings":
    st.header("Settings")
    st.write("Adjust preferences and learner info.")
    new_name = st.text_input("Learner display name", value=learner_name)
    if st.button("Save learner info"):
        store.add_learner(learner_id, new_name)
        st.success("Saved learner info.")

    st.markdown("---")
    st.write("UI Preferences")
    st.checkbox("Enable detailed logging", value=False, key='detailed_logging')
    st.checkbox("Show hints by default", value=True, key='show_hints')

elif page == "Search":
    st.header("Search Curriculum")
    q = st.text_input("Search items by text or id")
    results = []
    for skill_items in loader.by_skill.values():
        for it in skill_items:
            text = f"{it.get('id')} {it.get('stem_en', '')} {it.get('stem_fr', '')}"
            if not q or q.lower() in text.lower():
                results.append(it)

    st.write(f"Found {len(results)} items")
    cols = st.columns(2)
    for i, it in enumerate(results):
        with cols[i % 2]:
            st.markdown(f"**{it.get('id')}** — {it.get('stem_en')}")
            st.image(generate_visual(it), use_column_width=True)
            if st.button(f"Use this item", key=f"use_{it.get('id')}"):
                st.session_state.current_index = items.index(it) if it in items else 0
                st.success("Selected item for Play mode")

elif page == "Interactive Puzzle":
    st.header("Interactive Puzzle — Drag & Drop")
    items = loader.by_skill.get(selected_skill, [])
    if not items:
        st.warning("No items found for this skill.")
    else:
        item = items[st.session_state.current_index]
        count = item.get('answer_int') or 1

        # Build HTML/JS interactive zone
        html = f"""
        <style>
        .wrapper{{font-family: Arial, Helvetica, sans-serif;}}
        .board{{display:flex;gap:20px;align-items:flex-start}}
        .scene{{width:65%;background:linear-gradient(180deg,#fff8f0,#fff4ea);padding:18px;border-radius:14px;box-shadow:0 8px 20px rgba(0,0,0,0.08)}}
        .dots{{display:flex;flex-wrap:wrap;gap:12px;padding:12px}}
        .dot{{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;transform:translateY(0);transition:transform .35s ease, box-shadow .25s ease}}
        .dot.glow{{box-shadow:0 8px 24px rgba(255,165,80,0.35);transform:translateY(-6px) scale(1.05)}}
        .tray{{width:32%;padding:12px}}
        .tiles{{display:flex;flex-wrap:wrap;gap:10px}}
        .tile{{width:72px;height:72px;border-radius:12px;background:#fff;border:2px dashed #ffdca8;display:flex;align-items:center;justify-content:center;font-size:20px;cursor:grab;user-select:none;transition:transform .2s ease, box-shadow .2s ease}}
        .tile:active{{cursor:grabbing;transform:scale(.98)}}
        .dropzone{{margin-top:14px;padding:18px;border-radius:12px;background:#fff6e8;border:2px dashed #ffcc88;min-height:120px;display:flex;align-items:center;justify-content:center}}
        .msg{{margin-top:12px;font-weight:700}}
        </style>

        <div class="wrapper">
          <div class="board">
            <div class="scene">
              <h3 style="margin:0 0 8px 0">{item.get('stem_en')}</h3>
              <div class="dots" id="dots"></div>
              <div style="margin-top:8px;font-size:14px;color:#666">Drag the correct number tile into the drop area.</div>
            </div>
            <div class="tray">
              <div class="tiles" id="tiles"></div>
              <div class="dropzone" id="dropzone">Drop here</div>
              <div class="msg" id="msg"></div>
            </div>
          </div>
        </div>

        <script>
        const colors = ['#FF6347','#FFD700','#66CDAA','#87CEFA','#DDA0DD','#FFA07A','#98FB98'];
        const count = {count};
        const dots = document.getElementById('dots');
        for(let i=0;i<count;i++){{
            const d=document.createElement('div'); d.className='dot'; d.style.background=colors[i%colors.length]; d.innerText='';
            dots.appendChild(d);
        }}

        // build tiles up to max(9)
        const tiles = document.getElementById('tiles');
        const maxTile = Math.max(6, count+2);
        for(let n=1;n<=maxTile;n++){{
            const t=document.createElement('div'); t.className='tile'; t.draggable=true; t.innerText=n; t.dataset.val=n;
            t.addEventListener('dragstart', ev=>{{ ev.dataTransfer.setData('text/plain', ev.target.dataset.val); }});
            tiles.appendChild(t);
        }}

        const drop = document.getElementById('dropzone');
        drop.addEventListener('dragover', e=>{{ e.preventDefault(); drop.style.background='#fff2d9'; }});
        drop.addEventListener('dragleave', e=>{{ drop.style.background=''; }});
        drop.addEventListener('drop', e=>{{ e.preventDefault(); drop.style.background=''; const v = parseInt(e.dataTransfer.getData('text/plain'));
            const msg = document.getElementById('msg');
            if(v===count){{
                msg.innerText='🎉 Great! That is correct!'; msg.style.color='#198754';
                // animate dots
                document.querySelectorAll('.dot').forEach((el,i)=>{{ setTimeout(()=> el.classList.add('glow'), i*80); setTimeout(()=> el.classList.remove('glow'), 1000+i*80); }});
            }} else {{
                msg.innerText='Try again — not quite.'; msg.style.color='#c82333';
                // shake animation
                drop.animate([{{transform:'translateX(-6px)'}},{{transform:'translateX(6px)'}},{{transform:'translateX(0)'}}], {{duration:300}});
            }}
        }});
        </script>
        """

        components.html(html, height=520)

        st.markdown("---")
        st.write("If the child answered correctly, press the button below to log the response and reward them.")
        if st.button("Mark Correct"):
            store.add_response(learner_id, selected_skill, item.get('id'), True, 'interactive_drag')
            learner.record_response(selected_skill, True)
            st.success("Logged correct response — nice! 🎈")
        if st.button("Mark Incorrect"):
            store.add_response(learner_id, selected_skill, item.get('id'), False, 'interactive_drag')
            learner.record_response(selected_skill, False)
            st.info("Logged incorrect response — keep practicing.")

elif page in ["Play", "Full Puzzle"]:
    if not items:
        st.warning("No items found for this skill.")
    else:
        if st.session_state.current_index >= len(items):
            st.session_state.current_index = 0

        # always use the current index item for the puzzle or play modes
        item = items[st.session_state.current_index]

        col_main, col_side = st.columns([3, 1])

        with col_main:
            if page == "Full Puzzle":
                st.markdown(f"### 🧩 Full Puzzle — {item.get('stem_en')}  🎯")
                st.write("A bigger, more playful activity — tap the big buttons to answer.")

                img_path = generate_visual(item, width=900, height=540)
                st.image(img_path, use_column_width=True)

                # auto-speak the puzzle prompt once per item
                if voice_assistant and auto_speak and st.session_state.get('last_spoken') != item.get('id'):
                    try:
                        speak_text = f"How many objects do you see? {item.get('stem_en')}"
                        t = gTTS(text=speak_text, lang='en')
                        tfq = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                        t.save(tfq.name)
                        st.audio(tfq.name)
                    except Exception:
                        pass
                    st.session_state['last_spoken'] = item.get('id')

                st.markdown("**Question:** How many objects do you see?")
                correct = item.get('answer_int') or 1
                # build options with a few distractors
                opts = [correct, max(1, correct - 1), correct + 1, correct + 2]
                opts = list(dict.fromkeys(opts))
                random.shuffle(opts)

                cols_opts = st.columns(len(opts))
                for i, opt in enumerate(opts):
                    with cols_opts[i]:
                        if st.button(f"{opt} 👆", key=f"puzzle_{item.get('id')}_{opt}"):
                            if opt == correct:
                                fb = "Yay! You counted correctly!"
                                st.success(fb)
                                st.balloons()
                                st.session_state.score += 1
                            else:
                                fb = "Almost — try counting again!"
                                st.error(fb)

                            if voice_assistant:
                                try:
                                    t = gTTS(text=fb, lang='en')
                                    tfb = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                                    t.save(tfb.name)
                                    st.audio(tfb.name)
                                except Exception:
                                    pass

                if st.button("Show hint"):
                    hint = "Try counting the colorful circles from left to right."
                    if voice_assistant:
                        try:
                            t = gTTS(text=hint, lang='en')
                            tf = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                            t.save(tf.name)
                            st.audio(tf.name)
                        except Exception:
                            pass

            # Live Mode: capture microphone, transcribe and respond automatically
            if st.session_state.get('live_mode'):
                st.markdown("**Live Mode:** Listening for the child's voice and responding automatically.")
                webrtc_ctx = webrtc_streamer(key="live-audio", mode=WebRtcMode.SENDRECV, media_stream_constraints={"audio": True, "video": False})

                if webrtc_ctx and webrtc_ctx.audio_receiver:
                    try:
                        frames = webrtc_ctx.audio_receiver.get_frames(timeout=0.5)
                    except Exception:
                        frames = []

                    for frm in frames or []:
                        try:
                            arr = frm.to_ndarray()  # shape (n_channels, n_samples)
                            sr = frm.sample_rate
                            # write to temporary wav
                            tfw = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                            # soundfile expects shape (n_samples, n_channels)
                            sf.write(tfw.name, arr.T, sr)
                            # transcribe using existing ASR adapter
                            transcript = asr.transcribe(tfw.name)
                            if transcript and transcript.strip():
                                last = st.session_state.get('last_live_transcript')
                                if transcript != last:
                                    st.session_state['last_live_transcript'] = transcript
                                    st.markdown(f"**Heard:** {transcript}")
                                    # simple scoring/feedback path
                                    expected = item.get('answer_int')
                                    correct = ResponseScorer.score_response(expected, transcript, item)
                                    fb_text = FeedbackGenerator.generate_feedback(correct, 'en', expected)
                                    # TTS feedback
                                    if voice_assistant:
                                        try:
                                            t = gTTS(text=fb_text, lang='en')
                                            tfb = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                                            t.save(tfb.name)
                                            st.audio(tfb.name)
                                        except Exception:
                                            pass
                                    if correct:
                                        st.success(fb_text)
                                    else:
                                        st.error(fb_text)
                                    # advance item when correct
                                    if correct:
                                        st.session_state.current_index = (st.session_state.current_index + 1) % len(items)
                        except Exception:
                            pass

            elif st.session_state.play_mode:
                st.markdown(f"### {item.get('stem_en')}  🎯")
                st.write(item.get('stem_fr'))
                st.write(item.get('stem_kin'))

                img_path = generate_visual(item)
                st.image(img_path, use_column_width=True)

                if st.button("🔊 Play question"):
                    t = gTTS(text=item.get('stem_en'), lang='en')
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    t.save(tf.name)
                    st.audio(tf.name)

                st.markdown("---")
                st.write("Answer by typing or by uploading a short audio clip.")
                audio = st.file_uploader("Upload audio response (optional)", type=["wav", "mp3", "m4a"], key='resp_audio')
                text_resp = st.text_input("Child's response", key='resp_text')

                submitted = st.button("Submit Answer", key='submit_answer')

                if submitted:
                    transcript = ""
                    if audio is not None:
                        with st.spinner("Transcribing audio..."):
                            import tempfile as _tmp, os as _os

                            suffix = _os.path.splitext(audio.name)[1]
                            tf2 = _tmp.NamedTemporaryFile(delete=False, suffix=suffix)
                            tf2.write(audio.read())
                            tf2.flush()
                            tf2.close()
                            transcript = asr.transcribe(tf2.name)
                    elif text_resp:
                        transcript = text_resp
                    else:
                        st.warning("Please provide a response.")

                    if transcript:
                        st.markdown("**Transcript:**")
                        st.write(transcript)

                        expected = item.get('answer_int')
                        correct = ResponseScorer.score_response(expected, transcript, item)

                        learner.record_response(selected_skill, correct)
                        store.add_response(learner_id, selected_skill, item.get('id'), correct, transcript)

                        lang = asr.detect_language(transcript) if transcript else 'en'
                        fb_text = FeedbackGenerator.generate_feedback(correct, lang, expected)

                        # TTS feedback
                        t = gTTS(text=fb_text, lang='en')
                        tfb = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                        t.save(tfb.name)
                        st.audio(tfb.name)

                        if correct:
                            st.success(fb_text)
                            st.balloons()
                            st.session_state.score += 1
                        else:
                            st.error(fb_text)

                        st.session_state.current_index += 1

            else:
                # Non-play mode: show list and let user pick
                idx = st.selectbox("Choose item", list(range(len(items))), format_func=lambda i: items[i].get('id') + ' — ' + items[i].get('stem_en'))
                item = items[idx]
                st.image(generate_visual(item), use_column_width=True)
                st.write(item.get('stem_en'))
                st.write(item.get('stem_fr'))

        with col_side:
            st.markdown("**Player**")
            st.metric("Learner", learner_name)
            st.metric("Score", st.session_state.score)
            st.metric("Progress", f"{st.session_state.current_index}/{len(items)}")

            if st.button("Next Item"):
                st.session_state.current_index = (st.session_state.current_index + 1) % len(items)

            st.markdown("---")
            st.write("Tips for caregivers:")
            st.write("- Encourage the child to answer out loud; try the microphone upload.")
            st.write("- Use 'Play question' to repeat the prompt.")

        # show local stats
        if st.expander("Local stats"):
            stats = store.get_stats(learner_id)
            st.json(stats)

        # cleanup temp images older than session (not implemented)

st.markdown("---")
st.caption("Run locally: `streamlit run app.py` — works with gTTS and Pillow available.")
