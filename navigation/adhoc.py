import ast
import json
import os
import time
from io import BytesIO

import boto3
import openai
import requests
import streamlit as st
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

from helper_functions.core_helpers import list_files_in_folder


def rerun_app():
    st.experimental_rerun()


# Replace these with your own AWS credentials
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION")
openai.api_key = os.environ.get("OPENAI_API_KEY")


def trigger_airflow_dag(selected_file):
    """
    Triggers a DAG in Apache Airflow using its REST API.

    Parameters:
    selected_file (str): The name of the file that the DAG should process.

    Returns:
    tuple: A tuple containing a message indicating if the DAG was triggered successfully,
           the execution date of the DAG run, and the ID of the DAG run.
           If the DAG was not triggered successfully, returns an error message and None for the other values.
    """
    airflow_url = "http://34.138.127.169:8080/api/v1/dags/transcribe_dag/dagRuns"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Authorization": "Basic YWlyZmxvdzI6YWlyZmxvdzI=",
    }
    data = {"conf": {"selected_file": selected_file}}
    response = requests.post(airflow_url, headers=headers, json=data)
    if response.status_code == 200 or response.status_code == 201:
        response_json = response.json()
        return (
            "DAG triggered successfully",
            response_json["execution_date"],
            response_json["dag_run_id"],
        )
    else:
        return f"Error triggering DAG: {response.text}", None, None


def get_latest_dag_run(dag_id, run_id):
    """
    Retrieves the latest state of a DAG run in Apache Airflow using its REST API.

    Parameters:
    dag_id (str): The ID of the DAG to retrieve the run for.
    run_id (str): The ID of the run to retrieve the state for.

    Returns:
    str: The state of the DAG run. Returns None if an error occurred while retrieving the state.
    """
    airflow_url = f"http://34.138.127.169:8080/api/v1/dags/{dag_id}/dagRuns/{run_id}"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Authorization": "Basic YWlyZmxvdzI6YWlyZmxvdzI=",
    }
    response = requests.get(airflow_url, headers=headers)
    if response.status_code == 200:
        dag_run = response.json()
        print("DAG run:", dag_run)  # Add this line to print the DAG run
        return dag_run["state"]
    else:
        return None


def generate_presigned_url(
    bucket_name, object_key, aws_access_key, aws_secret_key, aws_region
):
    """
    Generates a pre-signed URL that can be used to access a private object in an S3 bucket.

    Parameters:
    bucket_name (str): The name of the S3 bucket that contains the object.
    object_key (str): The key of the object that the pre-signed URL will provide access to.
    aws_access_key (str): The access key for your AWS account.
    aws_secret_key (str): The secret key for your AWS account.
    aws_region (str): The name of the AWS region where the S3 bucket is located.

    Returns:
    str: A pre-signed URL that can be used to access the private object for a limited time.
    """
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
    )
    url = s3_client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket_name, "Key": object_key}, ExpiresIn=3600
    )
    return url


def get_generic_questions(dag_id, task_id, run_id):
    """
    Retrieves generic questions and their answers from a DAG task's XCom data in Apache Airflow using its REST API.

    Parameters:
    dag_id (str): The ID of the DAG that the task belongs to.
    task_id (str): The ID of the task to retrieve the XCom data for.
    run_id (str): The ID of the run that the task belongs to.

    Returns:
    dict: A dictionary containing generic questions and their answers retrieved from the task's XCom data.
          Returns None if an error occurred while retrieving the data.
    """
    airflow_url = f"http://34.138.127.169:8080/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/xcomEntries/default_question_answers"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Authorization": "Basic YWlyZmxvdzI6YWlyZmxvdzI=",
    }
    response = requests.get(airflow_url, headers=headers)
    if response.status_code == 200:
        xcom_data = response.json()
        xcom_data = response.json()
        return xcom_data["value"]
    else:
        return None


def get_transcript(dag_id, task_id, run_id):
    """
    Retrieves the transcript data from a DAG task's XCom data in Apache Airflow using its REST API.

    Parameters:
    dag_id (str): The ID of the DAG that the task belongs to.
    task_id (str): The ID of the task to retrieve the XCom data for.
    run_id (str): The ID of the run that the task belongs to.

    Returns:
    dict: A dictionary containing the transcript data retrieved from the task's XCom data.
          Returns None if an error occurred while retrieving the data.
    """
    airflow_url = f"http://34.138.127.169:8080/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/xcomEntries/transcript_data"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Authorization": "Basic YWlyZmxvdzI6YWlyZmxvdzI=",
    }
    response = requests.get(airflow_url, headers=headers)
    if response.status_code == 200:
        xcom_data = response.json()
        xcom_data = response.json()
        return xcom_data["value"]
    else:
        return None


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


# Define the Streamlit pages
def adhoc():
    st.header("Transcribe Audio")

    if "transcript_data" not in st.session_state:
        st.session_state.transcript_data = None

    if "generic_questions_dict" not in st.session_state:
        st.session_state.generic_questions_dict = None

    if "selected_file_name" not in st.session_state:
        st.session_state.selected_file_name = None

    if "qna" not in st.session_state:
        st.session_state.qna = None

    if not st.session_state.generic_questions_dict:
        # List files in the to_be_processed folder
        files_in_folder = list_files_in_folder(
            S3_BUCKET_NAME,
            "to_be_processed/",
            AWS_ACCESS_KEY,
            AWS_SECRET_KEY,
            AWS_REGION,
        )
        selected_file = st.selectbox(
            "Select an audio file to be processed:",
            files_in_folder,
            key="selected_file",
        )

        if selected_file and not st.session_state.generic_questions_dict:
            file = selected_file.split("/")[-1]
            st.text(f"Selected Audio File: {file}")
            # Generate a presigned URL for the selected file
            presigned_url = generate_presigned_url(
                S3_BUCKET_NAME,
                selected_file,
                AWS_ACCESS_KEY,
                AWS_SECRET_KEY,
                AWS_REGION,
            )
            st.audio(presigned_url, format="audio/mp3")

        if st.button("Transcribe to Text"):
            # Trigger the Airflow DAG
            result, _, run_id = trigger_airflow_dag(selected_file)
            if result == "DAG triggered successfully":
                dag_text = st.empty()
                dag_text.write(result)
                check_text = st.empty()
                check_text.warning("Transcribing Audio...")
                status_text = st.empty()  # Create an empty element to update the status

                time.sleep(5)  # Add a longer initial wait time

                # Periodically check the status and update the message
                dag_status = "running"
                while dag_status not in ["success", "failed"]:
                    try:
                        dag_status = get_latest_dag_run("transcribe_dag", run_id)
                    except Exception as e:
                        dag_text.empty()
                        check_text.empty()
                        st.error(f"An error occurred: {str(e)}")
                        break

                    if dag_status == "success":
                        json_file_name = selected_file.replace(
                            "to_be_processed/", "default_qna/"
                        ).replace(".mp3", ".json")
                        status_text.success("Audio successfully transcribed.")
                        dag_text.empty()
                        check_text.empty()
                        st.session_state.transcript_data = get_transcript(
                            "transcribe_dag", "transcribe_and_upload_s3", run_id
                        )
                        try:
                            json_contents = download_file_contents(
                                S3_BUCKET_NAME,
                                json_file_name,
                                AWS_ACCESS_KEY,
                                AWS_SECRET_KEY,
                                AWS_REGION,
                            )
                            st.session_state.qna = json.loads(json_contents)
                        except ClientError as e:
                            if e.response["Error"]["Code"] == "NoSuchKey":
                                st.warning(
                                    "No Q&A JSON file found for the selected transcript."
                                )

                        st.session_state.generic_questions_dict = get_generic_questions(
                            "transcribe_dag", "answer_default_questions", run_id
                        )
                        break
                    elif dag_status == "failed":
                        dag_text.empty()
                        check_text.empty()
                        status_text.error("Audio transcription failed.")
                    else:
                        status_text.success(f"Transcription status: {dag_status}")
                        time.sleep(10)  # Adjust the sleep time as needed

    if st.session_state.transcript_data:
        st.subheader("Audio to Text")
        st.text_area("Transcript:", value=st.session_state.transcript_data, height=200)

    if st.session_state.generic_questions_dict:
        question_list = list(st.session_state.qna.keys())
        selected_question = st.selectbox("Select a question:", question_list)
        if selected_question:
            answer = st.session_state.qna[selected_question]
            st.text_area("Answer:", value=answer, height=100)
        if st.button("Transcribe Different Audio File"):
            st.session_state.generic_questions_dict = None
            st.session_state.transcript_data = None
            rerun_app()
        if "conversation_history" not in st.session_state:
            st.session_state.conversation_history = []

        # Display previous questions and answers
        st.subheader("AI Chat Extravaganza")
        for i, qa in enumerate(st.session_state.conversation_history):
            role = "user" if i % 2 == 0 else "gpt-3.5-turbo"
            render_conversation(qa, role)

        # Add a new question input field and button
        new_question = st.text_input("Ask a new question:", key="adhoc_page")
        if st.button("Submit New Question"):
            prompt = f"{st.session_state.transcript_data}\n\n"
            for qa in st.session_state.conversation_history:
                prompt += f"{qa}\n"
            prompt += f"User: {new_question}\ngpt-3.5-turbo:"
            answer = get_gpt_answer(prompt)

            st.session_state.conversation_history.append(f"User: {new_question}")
            st.session_state.conversation_history.append(f"gpt-3.5-turbo: {answer}")
            st.text_area(f"gpt-3.5-turbo:", value=answer)
