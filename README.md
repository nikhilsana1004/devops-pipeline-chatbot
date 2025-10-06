# CI/CD Pipeline Chatbot

A Streamlit-based chatbot that uses AWS Bedrock (Claude) to provide intelligent insights about your CI/CD pipeline data stored in AWS Athena.

## 🌟 Features

- 🔍 Query CI/CD pipeline data using natural language
- 📊 Automatic data preprocessing and summary generation
- 🤖 AI-powered responses using AWS Bedrock (Claude 3 Sonnet)
- 💬 Interactive chat interface built with Streamlit
- ⚡ Real-time pipeline monitoring and analysis

## 🏗️ Architecture

- **Data Source**: AWS Athena
- **AI Model**: AWS Bedrock (Claude 3 Sonnet)
- **Frontend**: Streamlit
- **Storage**: AWS S3

## 📋 Prerequisites

- Python 3.8+
- AWS Account with access to:
  - Amazon Athena
  - Amazon S3
  - Amazon Bedrock
- AWS credentials configured (AWS CLI or IAM role)

## 🚀 Setup

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/devops-pipeline-chatbot.git
cd pipeline-chatbot