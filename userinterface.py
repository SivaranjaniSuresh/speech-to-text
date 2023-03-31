import streamlit as st

from navigation.adhoc import adhoc
from navigation.mp3_uploader import mp3_uploader
from navigation.questionnaire import questionnaire

# Define the Streamlit pages
pages = {
    "MP3 Uploader": mp3_uploader,
    "Adhoc": adhoc,
    "Questionnaire": questionnaire,
}


def main():
    st.sidebar.title("Navigation")
    if "current_page" not in st.session_state:
        st.session_state.current_page = ""
    selection = st.sidebar.radio("Go to", list(pages.keys()))

    # Clear session state if the current page is different from the previous page
    if selection != st.session_state.current_page:
        st.session_state.clear()
        st.session_state.current_page = selection

    page = pages[selection]
    page()


if __name__ == "__main__":
    main()
