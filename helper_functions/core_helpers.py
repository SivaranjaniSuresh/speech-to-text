import boto3
import streamlit as st


def upload_to_s3(file, s3_bucket, s3_key, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION):
    """
    Uploads a file to an Amazon S3 bucket.

    Parameters:
    file (file-like object): The file-like object to be uploaded to S3.
    s3_bucket (str): The name of the S3 bucket to upload the file to.
    s3_key (str): The name of the key that the file will be stored under in S3.
    AWS_ACCESS_KEY (str): The access key for your AWS account.
    AWS_SECRET_KEY (str): The secret key for your AWS account.
    AWS_REGION (str): The name of the AWS region where the S3 bucket is located.

    Returns:
    str: A message indicating if the file was uploaded successfully or if an error occurred.
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
    )

    try:
        s3.upload_fileobj(file, s3_bucket, s3_key)
        return f"Audio File Uploaded."
    except Exception as e:
        return f"Error: {str(e)}"


def list_files_in_folder(
    s3_bucket, folder_prefix, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
):
    """
    Lists all files in an Amazon S3 bucket that have a specified prefix.

    Parameters:
    s3_bucket (str): The name of the S3 bucket to list files from.
    folder_prefix (str): The prefix of the key for the files you want to list.
    AWS_ACCESS_KEY (str): The access key for your AWS account.
    AWS_SECRET_KEY (str): The secret key for your AWS account.
    AWS_REGION (str): The name of the AWS region where the S3 bucket is located.

    Returns:
    list: A list of all file names in the S3 bucket that have the specified prefix.
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
    )

    response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=folder_prefix)
    file_list = [
        content["Key"]
        for content in response.get("Contents", [])
        if content["Key"] != folder_prefix
    ]

    return file_list


def file_exists_in_s3(s3_bucket, s3_key, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION):
    """
    Checks if a file exists in an Amazon S3 bucket.

    Parameters:
    s3_bucket (str): The name of the S3 bucket to check for the file.
    s3_key (str): The key of the file to check for in the S3 bucket.
    AWS_ACCESS_KEY (str): The access key for your AWS account.
    AWS_SECRET_KEY (str): The secret key for your AWS account.
    AWS_REGION (str): The name of the AWS region where the S3 bucket is located.

    Returns:
    bool: True if the file exists in the S3 bucket, False otherwise.
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
    )

    try:
        s3.head_object(Bucket=s3_bucket, Key=s3_key)
        return True
    except Exception as e:
        return False


def move_file_in_s3(
    file_name,
    source_folder,
    destination_folder,
    s3_bucket,
    AWS_ACCESS_KEY,
    AWS_SECRET_KEY,
    AWS_REGION,
):
    """
    Moves a file from one folder to another in an Amazon S3 bucket.

    Parameters:
    file_name (str): The name of the file to be moved.
    source_folder (str): The name of the folder the file is currently in.
    destination_folder (str): The name of the folder to move the file to.
    s3_bucket (str): The name of the S3 bucket that contains the file.
    AWS_ACCESS_KEY (str): The access key for your AWS account.
    AWS_SECRET_KEY (str): The secret key for your AWS account.
    AWS_REGION (str): The name of the AWS region where the S3 bucket is located.

    Returns:
    None
    """
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
        st.write(
            f"Moved {file_name} from {source_folder} to {destination_folder} in {s3_bucket} bucket."
        )
    except Exception as e:
        st.warning(e)
