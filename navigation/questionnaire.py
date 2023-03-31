import json
import os

import boto3
import openai
import requests
import streamlit as st
from botocore.exceptions import ClientError

from helper_functions.core_helpers import list_files_in_folder

# Replace these with your own AWS credentials
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION")
openai.api_key = os.environ.get("OPENAI_API_KEY")


def download_file_contents(
    bucket_name, file_key, aws_access_key, aws_secret_key, aws_region
):
    """
    Downloads the contents of a file from an S3 bucket.

    Parameters:
    bucket_name (str): The name of the S3 bucket that contains the file.
    file_key (str): The key of the file to download.
    aws_access_key (str): The access key for your AWS account.
    aws_secret_key (str): The secret key for your AWS account.
    aws_region (str): The name of the AWS region where the S3 bucket is located.

    Returns:
    str: The contents of the file.
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
    )
    obj = s3.get_object(Bucket=bucket_name, Key=file_key)
    return obj["Body"].read().decode("utf-8")


def save_answers_to_s3(
    bucket_name,
    folder_name,
    answers,
    filename,
    aws_access_key,
    aws_secret_key,
    aws_region,
):
    """
    Saves a dictionary of answers to an S3 bucket as a JSON file.

    Parameters:
    bucket_name (str): The name of the S3 bucket to save the JSON file to.
    folder_name (str): The name of the folder within the bucket to save the file to.
    answers (dict): The dictionary of answers to save as a JSON file.
    filename (str): The name of the file to save the JSON data to.
    aws_access_key (str): The access key for your AWS account.
    aws_secret_key (str): The secret key for your AWS account.
    aws_region (str): The name of the AWS region where the S3 bucket is located.

    Returns:
    None
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
    )

    # Convert the answers dictionary to a JSON string
    answers_json = json.dumps(answers)

    # Use the provided filename for the JSON file
    filename = f"{folder_name}/{filename}"

    # Upload the JSON file to the S3 bucket
    s3.put_object(
        Bucket=bucket_name,
        Key=filename,
        Body=answers_json,
        ContentType="application/json",
    )


def get_gpt_answer(prompt):
    """
    Generates an AI-powered response using OpenAI's GPT-3.5 Turbo model.

    Parameters:
    prompt (str): The text prompt to generate a response for.

    Returns:
    str: The generated response from the GPT-3.5 Turbo model.
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,
        n=1,
        stop=None,
        temperature=0.6,
    )
    return response.choices[0].message["content"].strip()


def render_conversation(qa, role):
    """
    Renders a conversation message in a Streamlit app.

    Parameters:
    qa (str): The message to render.
    role (str): The role of the conversation participant (either 'user' or 'system').

    Returns:
    None
    """
    if role == "user":
        st.markdown(
            f'<p style="color:#1abc9c;font-size:18px;font-weight:bold;margin-bottom:2px;">{role.capitalize()}:</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="color:#ffffff;font-size:16px;margin-top:0px;">{qa[len(role) + 2:]}</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p style="color:#f63366;font-size:18px;font-weight:bold;margin-bottom:2px;">{role.capitalize()}:</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="color:#ffffff;font-size:16px;margin-top:0px;">{qa[len(role) + 2:]}</p>',
            unsafe_allow_html=True,
        )


def questionnaire():
    st.header("Questionnaire Page")
    files_in_folder = list_files_in_folder(
        S3_BUCKET_NAME, "transcripts/", AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
    )
    if "previous_selected_file" not in st.session_state:
        st.session_state.previous_selected_file = None

    if "file_conversation_history" not in st.session_state:
        st.session_state.file_conversation_history = {}

    selected_file = st.selectbox(
        "Select transcript:", files_in_folder, key="selected_file"
    )

    if st.session_state.previous_selected_file != selected_file:
        # Save the current conversation history
        if st.session_state.previous_selected_file is not None:
            st.session_state.file_conversation_history[
                st.session_state.previous_selected_file
            ] = st.session_state.conversation_history

        # Retrieve the conversation history for the newly selected file or create an empty list
        st.session_state.conversation_history = (
            st.session_state.file_conversation_history.get(selected_file, [])
        )

        st.session_state.previous_selected_file = selected_file
        st.experimental_rerun()

    if selected_file:
        if "conversation_history" not in st.session_state:
            st.session_state.conversation_history = []
        file_contents = download_file_contents(
            S3_BUCKET_NAME, selected_file, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
        )
        st.text_area("Transcript:", value=file_contents, height=200)

        # Retrieve the corresponding Q&A JSON file
        json_file_name = selected_file.replace("transcripts/", "default_qna/").replace(
            ".txt", ".json"
        )

        try:
            json_contents = download_file_contents(
                S3_BUCKET_NAME,
                json_file_name,
                AWS_ACCESS_KEY,
                AWS_SECRET_KEY,
                AWS_REGION,
            )
            qna_data = json.loads(json_contents)

            question_list = list(qna_data.keys())
            selected_question = st.selectbox("Select a question:", question_list)

            if selected_question:
                answer = qna_data[selected_question]
                st.text_area("Answer:", value=answer, height=100)

            # Display previous questions and answers
            st.subheader("AI Chat Extravaganza")
            for i, qa in enumerate(st.session_state.conversation_history):
                role = "user" if i % 2 == 0 else "gpt-3.5-turbo"
                render_conversation(qa, role)

            # Add a new question input field and button
            new_question = st.text_input(
                "Ask a new question:", key="questionnaire_page"
            )
            if st.button("Submit New Question"):
                prompt = f"{file_contents}\n\n"
                for qa in st.session_state.conversation_history:
                    prompt += f"{qa}\n"
                prompt += f"User: {new_question}\ngpt-3.5-turbo:"
                answer = get_gpt_answer(prompt)

                st.session_state.conversation_history.append(f"User: {new_question}")
                st.session_state.conversation_history.append(f"gpt-3.5-turbo: {answer}")
                st.text_area(f"gpt-3.5-turbo:", value=answer)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                st.warning("No Q&A JSON file found for the selected transcript.")
                if st.button("Generate:"):
                    default_questions = [
                        "How many speakers are there in the input string?",
                        "What is the tone or sentiment of the input string?",
                        "What is the purpose of the input string?",
                        "What is the audience for the input string?",
                        "Can you identify the key discussion points and decisions made during the meeting?",
                        "Could you analyze the sentiment of the participants throughout the meeting and identify any points of disagreement or consensus?",
                    ]

                    # Format the questions for the prompt
                    questions_formatted = "\n".join(
                        [f"{i + 1}. {q}" for i, q in enumerate(default_questions)]
                    )
                    prompt = f"Analyze the following input string and answer the default questions below:\n\nInput String: {file_contents}\n\nQuestions:\n{questions_formatted}\n\n"

                    # API call to OpenAI using the chat/completions endpoint
                    openai_api_key = openai.api_key
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {openai_api_key}",
                    }
                    data = {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": "Answer the questions."},
                        ],
                        "max_tokens": 200,
                        "temperature": 0.6,
                    }
                    response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=data,
                    )
                    response_json = response.json()

                    # Extract the answers from the response
                    answers_raw = (
                        response_json["choices"][0]["message"]["content"]
                        .strip()
                        .split("\n")
                    )
                    answers = {}

                    for i, question in enumerate(default_questions):
                        if i < len(answers_raw) and answers_raw[i].startswith(
                            f"{i + 1}."
                        ):
                            answer = answers_raw[i][len(str(i + 1)) + 2 :].strip()
                            answers[question] = answer
                            print(f"{question} Answer: {answer}")
                        else:
                            print(f"Error: could not find answer for question {i + 1}")
                    file_name = f"{selected_file.split('/')[-1].split('.')[0]}.json"
                    save_answers_to_s3(
                        bucket_name=S3_BUCKET_NAME,
                        folder_name="default_qna",
                        answers=answers,
                        filename=file_name,
                        aws_access_key=AWS_ACCESS_KEY,
                        aws_secret_key=AWS_SECRET_KEY,
                        aws_region=AWS_REGION,
                    )
                    st.success(f"Generated QnAs saved to {file_name}")
                    if "conversation_history" not in st.session_state:
                        st.session_state.conversation_history = []

                    # Display previous questions and answers
                    st.subheader("AI Chat Extravaganza")
                    for i, qa in enumerate(st.session_state.conversation_history):
                        role = "user" if i % 2 == 0 else "gpt-3.5-turbo"
                        render_conversation(qa, role)

                    # Add a new question input field and button
                    new_question = st.text_input("Ask a new question:")
                    if st.button("Submit New Question"):
                        prompt = f"{file_contents}\n\n"
                        for qa in st.session_state.conversation_history:
                            prompt += f"{qa}\n"
                        prompt += f"User: {new_question}\ngpt-3.5-turbo:"
                        answer = get_gpt_answer(prompt)

                        st.session_state.conversation_history.append(
                            f"User: {new_question}"
                        )
                        st.session_state.conversation_history.append(
                            f"gpt-3.5-turbo: {answer}"
                        )
                        st.text_area(f"gpt-3.5-turbo:", value=answer)
            else:
                st.error("Error while retrieving Q&A JSON file: ", e)
    else:
        st.write("No transcript files found.")
