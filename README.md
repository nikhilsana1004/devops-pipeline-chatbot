# 🚀 DevOps Pipeline Chatbot

> Talk to your CI/CD pipelines in natural language.  
> **v2 — Powered by AWS Strands Agents · Bedrock · Athena · CloudWatch · MCP**

[![CI](https://github.com/nikhilsana1004/devops-pipeline-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/nikhilsana1004/devops-pipeline-chatbot/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What's New in v2

| Feature | v1 | v2 |
|---|---|---|
| AI Call | `bedrock.invoke_model` (single call) | **Strands Agent** (agentic loop) |
| Tools | Athena only | **Athena + CloudWatch + CodePipeline + S3 + SNS** |
| Memory | ❌ Stateless | **✅ Conversation memory** across turns |
| MCP | ❌ | **✅ MCP Server** — connect from Claude Desktop / Kiro / Amazon Q |
| Suggested prompts | ❌ | **✅** |
| Tool-call inspector | ❌ | **✅** Expandable per response |
| Docker | ❌ | **✅** |
| Tests | ❌ | **✅** pytest + mocked AWS |
| CI | ❌ | **✅** GitHub Actions (Python 3.10/3.11/3.12) |

The original Athena schema is preserved exactly:
`account · time · region · pipeline · execution_id · start_time · stage · action · state`

---

## Architecture

```
User (Streamlit UI)
        │
        ▼
  PipelineAgent  ←  AWS Strands Agents SDK (agentic loop)
        │
        ├── query_athena()            SQL on pipeline_executions
        ├── get_pipeline_summary()    Overall counts & state breakdown
        ├── get_failed_pipelines()    Recent failures with stage/action
        ├── get_table_schema()        Column reference for SQL writing
        ├── get_cloudwatch_metrics()  Build counts, duration trends
        ├── get_cloudwatch_alarms()   Active alarm states
        ├── get_pipeline_status()     Real-time CodePipeline stage state
        ├── list_pipelines()          All pipelines in account
        ├── get_pipeline_executions() Execution history
        ├── list_s3_artifacts()       Browse build artifacts (optional)
        └── send_sns_alert()          Notify team (optional)

  MCP Server (mcp_servers/pipeline_mcp_server.py)
        └── Same tools exposed via Model Context Protocol
            Connect from: Claude Desktop · Kiro · Amazon Q CLI · Claude Code
```

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/nikhilsana1004/devops-pipeline-chatbot.git
cd devops-pipeline-chatbot

python -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your values
```

Minimum required:

```env
AWS_REGION=us-west-2
ATHENA_DATABASE=your_athena_database
ATHENA_TABLE=your_athena_table
ATHENA_OUTPUT_BUCKET=s3://your-bucket/athena-output/
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

### 3. Run

```bash
streamlit run app.py
# Open http://localhost:8501
```

---

## MCP Server

Expose your pipeline data to any MCP-compatible AI assistant:

```bash
python mcp_servers/pipeline_mcp_server.py
```

Add to your client config (e.g. `~/.aws/amazonq/mcp.json` for Amazon Q, `~/.kiro/settings/mcp.json` for Kiro):

```json
{
  "mcpServers": {
    "devops-pipeline": {
      "command": "python",
      "args": ["mcp_servers/pipeline_mcp_server.py"],
      "env": {
        "AWS_REGION": "us-west-2",
        "ATHENA_DATABASE": "your_database",
        "ATHENA_TABLE": "your_table",
        "ATHENA_OUTPUT_BUCKET": "s3://your-bucket/athena-output/"
      }
    }
  }
}
```

---

## Docker

```bash
docker build -t devops-pipeline-chatbot .

docker run -p 8501:8501 \
  -e AWS_REGION=us-west-2 \
  -e ATHENA_DATABASE=your_database \
  -e ATHENA_TABLE=your_table \
  -e ATHENA_OUTPUT_BUCKET=s3://your-bucket/athena-output/ \
  -v ~/.aws:/root/.aws:ro \
  devops-pipeline-chatbot
```

---

## Example Queries

| Query | Tools Used |
|---|---|
| "What is the status of the latest pipeline execution?" | `query_athena` |
| "Which pipelines failed in the last 24 hours?" | `get_failed_pipelines` |
| "Give me a summary of all pipeline activity" | `get_pipeline_summary` |
| "Show all pipelines running in us-east-1" | `query_athena` |
| "Which stage causes the most failures?" | `query_athena` |
| "Show build duration trend for api-pipeline" | `get_cloudwatch_metrics` |
| "Are there any active alarms?" | `get_cloudwatch_alarms` |
| "What's the current status of prod-deploy?" | `get_pipeline_status` |
| "Alert the team that api-pipeline is down" | `send_sns_alert` |

---

## Tests

```bash
pytest tests/ -v --cov=tools --cov=utils --cov=agents
```

---

## Project Structure

```
devops-pipeline-chatbot/
├── app.py                           Streamlit UI (v2)
├── agents/
│   └── pipeline_agent.py            Strands Agent orchestrator
├── tools/
│   ├── athena_tools.py              query_athena, get_pipeline_summary, get_failed_pipelines
│   ├── cloudwatch_tools.py          CloudWatch metrics & alarms
│   ├── codepipeline_tools.py        Live pipeline status & history
│   ├── s3_tools.py                  S3 artifact browser
│   └── sns_tools.py                 SNS alert publisher
├── mcp_servers/
│   └── pipeline_mcp_server.py       FastMCP server
├── utils/
│   ├── session.py                   Streamlit session helpers
│   └── formatters.py                Response formatters
├── tests/
│   └── test_tools.py                pytest tests (real schema)
├── .github/workflows/ci.yml         GitHub Actions CI
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## IAM Policy (minimum)

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "s3:GetObject", "s3:PutObject", "s3:ListBucket",
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:DescribeAlarms",
      "codepipeline:GetPipelineState",
      "codepipeline:ListPipelines",
      "codepipeline:ListPipelineExecutions",
      "glue:GetDatabase", "glue:GetTable"
    ],
    "Resource": "*"
  }]
}
```

---

## Roadmap

- [ ] Amazon Bedrock AgentCore serverless deployment
- [ ] Bedrock Knowledge Base for runbook RAG
- [ ] Multi-agent: health agent + remediation agent
- [ ] GitHub Actions / Jenkins MCP server
- [ ] Auto-remediation via Lambda on failure detection
- [ ] Voice interface via Bedrock Nova Sonic

---

## Contributing

```bash
git checkout -b feature/YourFeature
git commit -m "Add YourFeature"
git push origin feature/YourFeature
# Open a Pull Request
```

**Author:** Nikhil Sana · [@nikhilsana1004](https://github.com/nikhilsana1004)

⭐ Star this repo if it helped you!
