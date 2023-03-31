import os
from io import BytesIO

import boto3
import streamlit as st
from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv()
from helper_functions.core_helpers import (
    file_exists_in_s3,
    list_files_in_folder,
    upload_to_s3,
)

# Replace these with your own AWS credentials
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION")


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


def mp3_uploader():
    st.header("MP3 Uploader")
    uploaded_file = st.file_uploader("Choose an MP3 file", type="mp3")
    if uploaded_file is not None:
        file_size = len(uploaded_file.getvalue()) / (1024 * 1024)  # Convert bytes to MB

        if file_size > 25:
            st.error(
                "The uploaded file is too large (greater than 25 MB). Please upload a smaller file."
            )
        else:
            # Read the audio file
            audio = AudioSegment.from_file(uploaded_file)

            # Apply a low-pass filter to reduce noise
            filtered_audio = audio.low_pass_filter(1000)

            # Export the filtered audio as a MP3 file
            filtered_audio_data = BytesIO()
            filtered_audio.export(filtered_audio_data, format="mp3")
            filtered_audio_data.seek(0)

            if st.button("Upload to S3"):
                s3_key = f"to_be_processed/{uploaded_file.name}"

                if file_exists_in_s3(
                    S3_BUCKET_NAME, s3_key, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
                ):
                    st.warning("File already exists.")
                else:
                    upload_result = upload_to_s3(
                        filtered_audio_data,
                        S3_BUCKET_NAME,
                        s3_key,
                        AWS_ACCESS_KEY,
                        AWS_SECRET_KEY,
                        AWS_REGION,
                    )
                    st.success(upload_result)

    # List files in the to_be_processed folder
    files_in_folder = list_files_in_folder(
        S3_BUCKET_NAME, "to_be_processed/", AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
    )
    selected_file = st.selectbox(
        "Files in the to_be_processed folder:", files_in_folder
    )
    if selected_file:
        presigned_url = generate_presigned_url(
            S3_BUCKET_NAME, selected_file, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
        )
        st.audio(presigned_url, format="audio/mp3")
    else:
        st.warning("No files found to be processed.")
