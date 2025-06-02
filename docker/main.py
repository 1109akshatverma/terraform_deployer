from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import uuid
import boto3
import json
import shutil

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

S3_BUCKET = "pject-logs"
CREDENTIAL_STORE = {}

# 🔧 Replace with your actual EC2 details
EC2_IP = ""
SSH_KEY_PATH = ""
EC2_USER = "ec2-user"

@app.post("/upload")
async def upload_template(
    file: UploadFile = File(...),
    provider: str = Form(...),
    access_key_id: str = Form(None),
    secret_access_key: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
    tenant_id: str = Form(None),
    subscription_id: str = Form(None)
):
    deployment_id = str(uuid.uuid4())
    temp_dir = f"temp/{deployment_id}"
    os.makedirs(temp_dir, exist_ok=True)

    zip_path = f"{temp_dir}/template.zip"
    with open(zip_path, "wb") as f:
        f.write(await file.read())

    credentials = {"provider": provider}

    if provider == "aws":
        credentials.update({
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key
        })
    elif provider == "azure":
        credentials.update({
            "client_id": client_id,
            "client_secret": client_secret,
            "tenant_id": tenant_id,
            "subscription_id": subscription_id
        })
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    CREDENTIAL_STORE[deployment_id] = credentials
    boto3.client('s3').upload_file(zip_path, S3_BUCKET, f"templates/{deployment_id}/template.zip")

    return {"deployment_id": deployment_id}

@app.post("/deploy/{deployment_id}")
async def deploy(deployment_id: str):
    print("Starting deployment for ID:", deployment_id)
    temp_dir = f"temp/{deployment_id}"
    os.makedirs(temp_dir, exist_ok=True)
    zip_path = f"{temp_dir}/template.zip"
    creds_path = f"{temp_dir}/creds.json"

    s3 = boto3.client('s3')
    try:
        s3.download_file(S3_BUCKET, f"templates/{deployment_id}/template.zip", zip_path)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Template not found in S3: {str(e)}")

    credentials = CREDENTIAL_STORE.get(deployment_id)
    if not credentials:
        raise HTTPException(status_code=400, detail="Credentials not found for deployment")

    with open(creds_path, "w") as f:
        json.dump(credentials, f)

    remote_dir = f"/home/{EC2_USER}/{deployment_id}"
    try:
        subprocess.run(["ssh", "-i", SSH_KEY_PATH, f"{EC2_USER}@{EC2_IP}", f"mkdir -p {remote_dir}"], check=True)
        subprocess.run(["scp", "-i", SSH_KEY_PATH, zip_path, f"{EC2_USER}@{EC2_IP}:{remote_dir}/template.zip"], check=True)
        subprocess.run(["scp", "-i", SSH_KEY_PATH, creds_path, f"{EC2_USER}@{EC2_IP}:{remote_dir}/creds.json"], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"SCP/SSH to EC2 failed: {e}")

    remote_docker_cmd = (
        f'docker run --rm -v {remote_dir}:/app/workspace '
        f'terraform-executor5 '
        f'python3 /app/orchestration.py /app/workspace/template.zip {deployment_id} /app/workspace/creds.json'
    )

    ssh_cmd = f'ssh -i {SSH_KEY_PATH} {EC2_USER}@{EC2_IP} "{remote_docker_cmd}"'

    print("Running remote Docker command...")
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, shell=True)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        # Clean up 
        if result.returncode == 0:
            try:
                subprocess.run(
                    ["ssh", "-i", SSH_KEY_PATH, f"{EC2_USER}@{EC2_IP}", f"sudo rm -rf {remote_dir}"],
                    check=True
                )
                print(f"✅ Remote directory {remote_dir} deleted successfully.")
            except subprocess.CalledProcessError as cleanup_error:
                print(f"⚠️ Warning: Failed to delete remote directory {remote_dir}: {cleanup_error}")

        result_json = json.loads(result.stdout)
        return result_json

    except json.JSONDecodeError:
        print("Error decoding JSON from remote Docker output.")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        raise HTTPException(status_code=500, detail=f"Deployment failed: {result.stderr}")

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

@app.get("/status/{deployment_id}")
async def get_status(deployment_id: str):
    s3 = boto3.client('s3')
    try:
        output_obj = s3.get_object(Bucket=S3_BUCKET, Key=f"outputs/{deployment_id}/outputs.json")
        outputs = json.loads(output_obj["Body"].read().decode("utf-8"))

        formatted_outputs = "\n".join([
            f"{key} : {val.get('value', 'N/A')}" for key, val in outputs.items()
        ])
        summary = (
            "Deployment Status : Success\n"
            "Output Parameters :\n" + formatted_outputs
        )

        return {
            "status": "success",
            "summary": summary,
            "outputs": outputs
        }
    except s3.exceptions.NoSuchKey:
        return {"status": "pending or failed"}
