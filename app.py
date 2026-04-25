import streamlit as st
from core import (
    CurriculumLoader,
    ChildASRAdapter,
    ResponseScorer,
    LearnerState,
    LocalProgressStore,
    FeedbackGenerator,
)


st.set_page_config(page_title="AIMS Tutor Demo", layout="wide")


@st.cache_resource
def get_resources():
    loader = CurriculumLoader()
    asr = ChildASRAdapter()
    store = LocalProgressStore()
    return loader, asr, store


loader, asr, store = get_resources()


st.title("AIMS Tutor — Interactive Demo")
st.write("A playful Streamlit UI that demonstrates curriculum items, scoring, and knowledge tracing.")


with st.sidebar:
    st.header("Learner")
    learner_id = st.text_input("Learner ID", value="learner_001")
    learner_name = st.text_input("Name", value="Alex")
    skill_options = list(loader.by_skill.keys()) or ["counting"]
    selected_skill = st.selectbox("Skill", skill_options)
    st.markdown("---")
    st.caption("You can either type a response or upload a short audio file (wav/mp3). ASR will be used if available.")


learner = LearnerState(learner_id)
store.add_learner(learner_id, learner_name)


items = loader.by_skill.get(selected_skill, [])
item_index = st.selectbox("Choose item", list(range(len(items))), format_func=lambda i: items[i].get('id') + ' — ' + items[i].get('stem_en')) if items else None

if items:
    item = items[item_index]
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(item.get('stem_en'))
        st.write(item.get('stem_fr'))
        st.write(item.get('stem_kin'))
        st.info(f"Item: {item.get('id')} — difficulty {item.get('difficulty')}")

        audio = st.file_uploader("Upload audio response (optional)", type=["wav", "mp3", "m4a"])
        text_resp = st.text_input("Or type the child's response here")

        submitted = st.button("Submit Response")

        if submitted:
            transcript = ""
            if audio is not None:
                with st.spinner("Transcribing audio..."):
                    # Save uploaded file to a temp path for ASR
                    import tempfile, os

                    suffix = os.path.splitext(audio.name)[1]
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    tf.write(audio.read())
                    tf.flush()
                    tf.close()
                    transcript = asr.transcribe(tf.name)
            elif text_resp:
                transcript = text_resp
            else:
                st.warning("Please provide a typed response or upload audio.")

            if transcript:
                st.markdown("**Transcript:**")
                st.write(transcript)

                expected = item.get('answer_int')
                correct = ResponseScorer.score_response(expected, transcript, item)

                # store and update learner model
                learner.record_response(selected_skill, correct)
                store.add_response(learner_id, selected_skill, item.get('id'), correct, transcript)

                # feedback
                lang = asr.detect_language(transcript) if transcript else 'en'
                fb = FeedbackGenerator.generate_feedback(correct, lang, expected)

                if correct:
                    st.success(fb)
                else:
                    st.error(fb)

                # show knowledge trace
                p_learned = learner.skills[selected_skill].p_learned
                st.markdown("**Estimated mastery (BKT)**")
                st.progress(p_learned)

                # quick stats
                stats = store.get_stats(learner_id)
                st.markdown("**Local stats**")
                st.json(stats)

    with col2:
        st.metric("Learner ID", learner_id)
        st.metric("Responses logged", learner.response_count)
        st.markdown("---")
        st.write("Tips:")
        st.write("- Try typing 'three' or '3' for counting items.")
        st.write("- Upload a short audio clip to exercise ASR (if installed).")

else:
    st.warning("No items found for this skill.")


st.markdown("---")
st.caption("Created with core.py classes — a simple interactive demo. Run with: `streamlit run app.py`")
