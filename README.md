# Terraform Cloud Deployer – Guide

## 📐 Architecture Overview

### Architecture Diagram

```
+-------------------+
|     User GUI      |
|   (index.html)    |
+-------------------+
          |
          v
+-----------------------------+
|        FastAPI (main.py)    |
|  - Accepts zip & credentials|
|  - Uploads to S3            |
|  - Triggers EC2 deployment  |
+-----------------------------+
          |
          v
+-----------------------------+
|     EC2 Instance (Linux)    |
|   +----------------------+  |
|   | Docker Container     |  |
|   | - Runs orchestration.py |
|   | - Extracts zip       |  
|   | - Runs Terraform     |  
|   +----------------------+  |
|   Outputs logged to S3      |
+-----------------------------+
```

---

## 📖 Project Overview

The **Terraform Cloud Deployer** is an end-to-end system that allows non-technical or semi-technical users to deploy Terraform templates directly from a browser, without requiring local Terraform setup. Here's how the system works:

1. **Frontend (`index.html`)**  
   - Users select the cloud provider (AWS or Azure), upload a `.zip` containing Terraform code, and enter credentials.
   - On clicking **Deploy**, the form data is sent to the backend.

2. **FastAPI Backend (`main.py`)**  
   - Accepts the uploaded zip and credentials.
   - Stores the Terraform zip in an S3 bucket.
   - Stores credentials temporarily in `creds.json`.
   - Sends both to a remote EC2 instance using **SSH + SCP**.
   - Triggers a **Docker container** on EC2 that executes Terraform using `orchestration.py`.

3. **EC2 + Docker Execution (`orchestration.py`)**  
   - Docker container extracts the template, sets cloud-specific environment variables, and runs `terraform init`, `plan`, and `apply`.
   - Outputs and logs are stored in S3 (under `logs/` and `outputs/` folders).

4. **Frontend Status Check**  
   - After deployment, the frontend fetches status via `GET /status/{deployment_id}`.
   - Displays formatted Terraform outputs like public IP, instance ID, etc.

This makes infrastructure provisioning simple, repeatable, and secure—all via a browser.

---

## 🧰 Technologies Used

HTML, CSS, JavaScript, FastAPI, Uvicorn, Python, Docker, EC2, S3, Boto3, Terraform CLI, SSH, SCP, zipfile, subprocess, Azure ARM, IAM, JSON, python-multipart, CORS middleware.

---

## ⚙️ Setup Guide

### 1. EC2 Setup (Terraform Executor VM)

* Launch a **Linux EC2 instance** (Amazon Linux 2 or Ubuntu recommended).
* SSH into your instance.
* Install Docker:

```bash
sudo yum update -y
sudo yum install docker -y 
sudo service docker start
sudo usermod -a -G docker ec2-user
```

* Replace `m-a-k` with `ACCESS_KEY`, `a-s-k` with `SECRET_KEY` in `orchestration.py`.
* Transfer the `Dockerfile` and `orchestration.py` to the EC2 instance.
* Place your `.pem` key inside `docker` folder
* Build the Docker image:

```bash
docker build -t terraform-executor5 .
```

* Make sure the EC2 has IAM role or access to upload logs to S3.

### 2. FastAPI App Setup (Your Local/Backend Server)

* Clone the repo containing `main.py`, `index.html`, and dependencies.
* Replace `S3_BUCKET`, `EC2_IP`, `SSH_KEY_PATH`, and `EC2_USER` in `main.py`.
* Install Python dependencies:

```bash
pip install fastapi uvicorn boto3 python-multipart
```

* Ensure your private SSH key to connect with EC2 is available and named correctly in `main.py` (`SSH_KEY_PATH`).
* Run FastAPI server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. S3 Bucket Configuration

* Create a bucket (e.g., `pject-logs`) in logs account.

* Set appropriate bucket policies to allow access from EC2 and FastAPI.

### 4. Frontend (index.html)

* Open `index.html` in a browser (open locally).
* Upload `.zip` file containing Terraform templates.
* Choose a cloud provider (AWS/Azure).
* Enter the required credentials.
* Click **Deploy**.
* Monitor progress and view outputs directly on the page.

---

## 🔐 Security Considerations

### Credential Handling

* Credentials are submitted from frontend and stored in-memory using Python dict `CREDENTIAL_STORE`.
* Temporarily written to a file and SCP'ed to EC2.
* Deleted after the Terraform run is complete.

### Hardcoded AWS Keys (⚠️ Risk)

In `orchestration.py`, access keys are hardcoded:

```python
MY_ACCESS_KEY = "AKIA..."
MY_SECRET_KEY = "qhxR..."
```

✅ **Fix Recommendation**:

* Use environment variables.
* Configure IAM role for EC2 with S3 access.
* Use AWS Secrets Manager or Azure Key Vault for storing secrets.

### General Security Tips

* Always encrypt sensitive data.
* Use HTTPS for backend API endpoints.
* Sanitize all logs and never expose secrets.
* Limit S3 bucket access using IAM roles and bucket policies.

---


## 📘 User Manual

### Outputs Endpoint

* `GET /status/{deployment_id}`
* Sample output:

```json
{
  "status": "success",
  "outputs": {
    "public_ip": {"value": "3.87.100.50"}
  }
}
```

---

## 💰 Cost Estimation and Optimization

| Component           | Approximate Cost |
| ------------------- | ---------------- |
| EC2 Instance        | \$8 – \$30/month |
| S3 Storage          | \$0.023/GB/month |
| Terraform Resources | Varies by usage  |

### Optimization Tips

* Use **Free Tier** eligible EC2 types (e.g., `t2.micro`).
* Use **Spot Instances** for Terraform executor.
* Automatically destroy resources after use.
* Enable **lifecycle rules** for log cleanup.
* Compress logs before uploading to S3.

---

## ✅ Future Enhancements

* Add login/auth to UI (e.g., JWT or session-based auth).
* Store secrets securely (HashiCorp Vault, AWS Secrets Manager).
* Add error dashboard with real-time logs.
* Enable `terraform destroy` for cleanup.
* Accept Git repo URLs as input.
* Variable injection from frontend.
* Add support for more cloud providers.

---

## 📄 Files Overview

| File               | Purpose                                  |
| ------------------ | ---------------------------------------- |
| `index.html`       | Frontend form for user input and UI      |
| `main.py`          | FastAPI backend, handles upload & deploy |
| `orchestration.py` | Runs Terraform in Docker on EC2          |
| `Dockerfile`       | Defines Docker container for Terraform   |
