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
    page = st.selectbox("Page", ["Play", "Full Puzzle"])
    st.checkbox("Play mode (one item at a time)", value=True, key='play_mode')


if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
    st.session_state.score = 0


learner = LearnerState(learner_id)
store.add_learner(learner_id, learner_name)


items = loader.by_skill.get(selected_skill, [])

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
                            st.success("Yay! You counted correctly!")
                            st.balloons()
                            st.session_state.score += 1
                        else:
                            st.error("Almost — try counting again!")

            if st.button("Show hint"):
                hint = "Try counting the colorful circles from left to right."
                t = gTTS(text=hint, lang='en')
                tf = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                t.save(tf.name)
                st.audio(tf.name)

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
