import logging
import os
from urllib.parse import urlparse

import py7zr
import requests
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.sdk import Asset, asset

RAW_BUCKET_NAME = os.environ.get("RAW_BUCKET_NAME", "dak-platform")
RAW_PREFIX = "raw"
posts_asset = Asset(f"s3://{RAW_BUCKET_NAME}/{RAW_PREFIX}/Posts.xml")
users_asset = Asset(f"s3://{RAW_BUCKET_NAME}/{RAW_PREFIX}/Users.xml")


@asset.multi(schedule="@daily", outlets=[posts_asset, users_asset])
def produce_data_assets():
    # Define variables to download file and where to unzip
    key = "ai.meta.stackexchange.com"
    url = f"https://archive.org/download/stackexchange/{key}.7z"
    output_path = f"/tmp/{key}.7z"
    extract_path = f"/tmp/{key}"
    bucket_name = urlparse(posts_asset.name).netloc

    # Download the file
    logging.info(f"Downloading {url} to {output_path}")
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    with open(output_path, "wb") as file:
        file.write(response.content)

    # Extract the zipped file
    logging.info(f"Extracting {output_path} to {extract_path}")
    os.makedirs(extract_path, exist_ok=True)
    with py7zr.SevenZipFile(output_path, mode="r") as archive:
        archive.extractall(path=extract_path)

    # Load the file to S3
    s3_hook = S3Hook(aws_conn_id="aws_conn")
    posts_file = os.path.join(extract_path, "Posts.xml")
    users_file = os.path.join(extract_path, "Users.xml")
    s3_hook.load_file(
        filename=posts_file,
        key=f"{RAW_PREFIX}/Posts.xml",
        bucket_name=bucket_name,
        replace=True
    )
    s3_hook.load_file(
        filename=users_file,
        key=f"{RAW_PREFIX}/Users.xml",
        bucket_name=bucket_name,
        replace=True
    )
