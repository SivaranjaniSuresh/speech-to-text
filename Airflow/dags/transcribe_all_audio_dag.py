import json
import os
from datetime import datetime, timedelta
from io import BytesIO

import boto3
import openai
import requests
from airflow.operators.python_operator import PythonOperator
from dotenv import load_dotenv

from airflow import DAG

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

dag = DAG(
    "transcribe_all_audio_daily",
    default_args=default_args,
    description="Transcribe all audio files daily and move them to the appropriate folders",
    schedule_interval="0 0 * * *",
    start_date=datetime(2023, 3, 22),
    catchup=False,
)

# Replace these with your own AWS credentials
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = "us-east-1"
S3_BUCKET_NAME = "damg7245-team4-assignment-4-2"
openai.api_key = os.environ.get("OPENAI_API_KEY")

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
)


def upload_to_s3(file, s3_bucket, s3_key, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
    )

    try:
        s3.upload_fileobj(file, s3_bucket, s3_key)
        return f"File uploaded to {s3_bucket}/{s3_key}"
    except Exception as e:
        return f"Error: {str(e)}"


def move_file_in_s3(
    file_name,
    source_folder,
    destination_folder,
    s3_bucket,
    AWS_ACCESS_KEY,
    AWS_SECRET_KEY,
    AWS_REGION,
):
    try:
        s3 = boto3.resource(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
        )
        old_key = f"{source_folder}/{file_name}"
        new_key = f"{destination_folder}/{file_name}"
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
        )
        s3_client.copy_object(
            Bucket=s3_bucket,
            CopySource={"Bucket": s3_bucket, "Key": old_key},
            Key=new_key,
        )
        s3.Object(s3_bucket, old_key).delete()
        return f"Moved {file_name} from {source_folder} to {destination_folder} in {s3_bucket} bucket."
    except Exception as e:
        return e


class BytesIOWithName(BytesIO):
    def __init__(self, *args, **kwargs):
        self._name = kwargs.pop("name", "file.mp3")
        super(BytesIOWithName, self).__init__(*args, **kwargs)

    @property
    def name(self):
        return self._name


def push_s3_link_to_xcom(**kwargs):
    selected_file = kwargs["dag_run"].conf["selected_file"]
    if selected_file:
        kwargs["ti"].xcom_push(key="selected_file", value=selected_file)
        print(selected_file)
    else:
        raise ValueError("selected_file is not provided.")


def save_answers_to_s3(
    bucket_name,
    folder_name,
    answers,
    filename,
    aws_access_key,
    aws_secret_key,
    aws_region,
):
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


def get_default_questions_from_s3(bucket_name, file_key, s3_client):
    obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def transcribe_and_upload_s3_task(selected_file, kwargs):
    s3_file_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{selected_file}"
    print(s3_file_url)
    response = requests.get(s3_file_url)
    audio = BytesIOWithName(response.content, name=selected_file)
    transcript = openai.Audio.transcribe("whisper-1", audio)

    print(transcript["text"])

    transcript_file_name = f"{selected_file.split('/')[-1].split('.')[0]}.txt"
    transcript_key = f"transcripts/{transcript_file_name}"
    transcript_data = BytesIO(transcript["text"].encode("utf-8"))
    kwargs["ti"].xcom_push(key="transcript_file_name", value=transcript_file_name)

    try:
        upload_result = upload_to_s3(
            transcript_data,
            S3_BUCKET_NAME,
            transcript_key,
            AWS_ACCESS_KEY,
            AWS_SECRET_KEY,
            AWS_REGION,
        )
        if upload_result:
            file_name = selected_file.split("/")[-1]
            print("Uploading complete. Moving file to Archived.")
        else:
            raise Exception("Upload to S3 failed.")

    except Exception as e:
        # Log the error message
        print(f"Error while uploading transcript to S3: {e}")
        # Raise an AirflowSkipException to indicate that the task should be retried
        raise AirflowSkipException("Retrying task due to S3 upload failure.")

    try:
        move_file_in_s3(
            file_name,
            "to_be_processed",
            "archived",
            S3_BUCKET_NAME,
            AWS_ACCESS_KEY,
            AWS_SECRET_KEY,
            AWS_REGION,
        )
        print("Moved to Archived.")

    except Exception as e:
        # Log the error message
        print(f"Error while moving file to Archived: {e}")

    kwargs["ti"].xcom_push(key="transcript_data", value=transcript["text"])

    default_questions = get_default_questions_from_s3(
        S3_BUCKET_NAME, "default_qna/default_questions.json", s3_client
    )
    print(default_questions)

    # Format the questions for the prompt
    questions_formatted = "\n".join(
        [f"{i + 1}. {q}" for i, q in enumerate(default_questions)]
    )
    prompt = f"Analyze the following input string and answer the default questions below:\n\nInput String: {transcript['text']}\n\nQuestions:\n{questions_formatted}\n\n"

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
        "max_tokens": 250,
        "temperature": 0.6,
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions", headers=headers, json=data
    )
    response_json = response.json()

    # Extract the answers from the response
    answers_raw = response_json["choices"][0]["message"]["content"].strip().split("\n")
    answers = {}

    for i, question in enumerate(default_questions):
        if i < len(answers_raw) and answers_raw[i].startswith(f"{i + 1}."):
            answer = answers_raw[i][len(str(i + 1)) + 2 :].strip()
            answers[question] = answer
            print(f"{question} Answer: {answer}")
        else:
            print(f"Error: could not find answer for question {i + 1}")

    # Push the answers to XCom for future reference
    kwargs["ti"].xcom_push(key="default_question_answers", value=answers)

    file_name = f"{transcript_file_name.split('/')[-1].split('.')[0]}.json"
    save_answers_to_s3(
        S3_BUCKET_NAME,
        "default_qna",
        answers,
        file_name,
        AWS_ACCESS_KEY,
        AWS_SECRET_KEY,
        AWS_REGION,
    )
    return "Done Everything"


def list_files_in_s3_folder(
    s3_bucket, folder, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
    )
    result = s3.list_objects_v2(Bucket=s3_bucket, Prefix=folder)
    file_list = [
        content["Key"]
        for content in result.get("Contents", [])
        if content["Key"] != folder
    ]
    return file_list


def transcribe_and_upload_all_files_task(**kwargs):
    files_to_process = list_files_in_s3_folder(
        S3_BUCKET_NAME,
        "to_be_processed/",
        AWS_ACCESS_KEY,
        AWS_SECRET_KEY,
        AWS_REGION,
    )
    for selected_file in files_to_process:
        print(selected_file)
        transcribe_and_upload_s3_task(selected_file=selected_file, kwargs=kwargs)


transcribe_and_upload_all_files = PythonOperator(
    task_id="transcribe_and_upload_all_files",
    python_callable=transcribe_and_upload_all_files_task,
    provide_context=True,
    dag=dag,
)


transcribe_and_upload_all_files
