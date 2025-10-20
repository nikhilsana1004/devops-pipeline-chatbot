# 🚀 CI/CD Pipeline Chatbot

A Streamlit-based chatbot powered by AWS Bedrock (Claude 3.5 Sonnet) that provides intelligent insights on CI/CD pipeline data stored in AWS Athena.

## 🌟 Features
- Query pipeline data in natural language
- AI-powered analysis using AWS Bedrock
- Interactive Streamlit UI
- Real-time pipeline monitoring
- Automatic Athena data summarization

## 🏗️ Architecture
Data Source: AWS Athena  
Model: Claude 3 Sonnet (Bedrock)  
Frontend: Streamlit  
Storage: S3  

## 📋 Prerequisites
- Python ≥ 3.8  
- AWS account with Athena, S3, and Bedrock access  
- AWS CLI configured  
- Basic CI/CD knowledge  
- Read the prerequisites text file

## ⚙️ Quick Start

# 1. Clone the repository
git clone https://github.com/nikhilsana1004/devops-pipeline-chatbot.git
cd devops-pipeline-chatbot

# 2. Setup environment
python -m venv venv
source venv/bin/activate       # On macOS/Linux
venv\Scripts\activate          # On Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure AWS
aws configure

# 5. Setup environment variables
cp .env.example .env
Edit .env with your AWS configuration:

env
Copy code
AWS_REGION=us-west-2
ATHENA_DATABASE=your_athena_database
ATHENA_TABLE=your_athena_table
ATHENA_OUTPUT_BUCKET=s3://your-bucket/athena-output/
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
▶️ Run the App
bash
Copy code
streamlit run app.py
Access the app at: http://localhost:8501

💬 Example Queries
“Status of latest pipeline execution?”

“Pipelines failed in last 24 hrs?”

“Show all pipelines in us-east-1”

“Which pipeline has the most failures?”

🔒 Security Best Practices
Never commit .env or AWS credentials

Use IAM roles where possible

Apply least-privilege policies

Rotate keys regularly

🐛 Troubleshooting
Issue	Fix
No data found	Verify Athena DB/table names & permissions
Bedrock API errors	Confirm region and model access
S3 permission denied	Check bucket path and policies
AWS credentials missing	Run aws configure again

🤝 Contributing
bash
Copy code
git checkout -b feature/AmazingFeature
git commit -m "Add AmazingFeature"
git push origin feature/AmazingFeature
Follow Python best practices and test locally.


📧 Contact
Author: Nikhil Sana
GitHub: @nikhilsana1004
Project Link: devops-pipeline-chatbot

🗺️ Roadmap
Multi-source pipeline support

Advanced visualizations & reports

Docker containerization

Authentication & user management

Integration with other LLMs

⭐ If you find this helpful, give it a star!