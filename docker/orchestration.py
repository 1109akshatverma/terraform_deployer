import os
import subprocess
import zipfile
import boto3
import json
import sys
import re

def extract_zip(zip_path, dest):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest)

def strip_ansi_codes(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def run_terraform(workspace, user_credentials, deployment_id):
    provider = user_credentials['provider']

    if provider == "aws":
        os.environ['AWS_ACCESS_KEY_ID'] = user_credentials['access_key_id']
        os.environ['AWS_SECRET_ACCESS_KEY'] = user_credentials['secret_access_key']
    elif provider == "azure":
        os.environ['ARM_CLIENT_ID'] = user_credentials['client_id']
        os.environ['ARM_CLIENT_SECRET'] = user_credentials['client_secret']
        os.environ['ARM_TENANT_ID'] = user_credentials['tenant_id']
        os.environ['ARM_SUBSCRIPTION_ID'] = user_credentials['subscription_id']
    else:
        return {
            "status": "failed",
            "message": "Unsupported provider"
        }

    m-a-k = ""
    a-s-k = ""
    MY_S3_BUCKET = "pject-logs"

    logging_s3 = boto3.client(
        's3',
        aws_access_key_id=m-a-k,
        aws_secret_access_key=m-s-k
    )

    try:
        subprocess.run(["terraform", "init"], cwd=workspace, check=True, capture_output=True, text=True)
        subprocess.run(["terraform", "plan", "-out=tfplan"], cwd=workspace, check=True, capture_output=True, text=True)
        result = subprocess.run(["terraform", "apply", "tfplan"], cwd=workspace, check=True, capture_output=True, text=True)
        output = subprocess.run(["terraform", "output", "-json"], cwd=workspace, check=True, capture_output=True, text=True)
        outputs = json.loads(output.stdout)
    except subprocess.CalledProcessError as e:
        logging_s3.put_object(Bucket=MY_S3_BUCKET, Key=f"logs/{deployment_id}/error.log", Body=e.stderr)
        return {
            "status": "failed",
            "message": "Terraform execution failed.",
            "error": e.stderr
        }

    logging_s3.put_object(Bucket=MY_S3_BUCKET, Key=f"logs/{deployment_id}/terraform.log", Body=strip_ansi_codes(result.stdout))
    logging_s3.put_object(Bucket=MY_S3_BUCKET, Key=f"outputs/{deployment_id}/outputs.json", Body=json.dumps(outputs))

    formatted_outputs = "\n".join([
        f"{key} : {val.get('value', 'N/A')}" for key, val in outputs.items()
    ])

    summary = (
        "Deployment Status : Success\n"
        "Output Parameters :\n" + formatted_outputs
    )

    return {
        "status": "success",
        "message": "Deployment completed successfully.",
        "summary": summary,
        "outputs": outputs
    }

if __name__ == "__main__":
    zip_path = sys.argv[1]
    deployment_id = sys.argv[2]
    creds_file_path = sys.argv[3]

    with open(creds_file_path, "r") as f:
        user_credentials = json.load(f)

    extract_zip(zip_path, f"/app/workspace/{deployment_id}")
    result = run_terraform(f"/app/workspace/{deployment_id}", user_credentials, deployment_id)
    print(json.dumps(result))
