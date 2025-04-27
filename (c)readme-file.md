# Agentic AI Fund Search

A production-grade FastAPI application with an agentic AI system using LangGraph for intelligent search, summarization, and reasoning over mutual fund data from MFAPI.in.

## Features

- **Agentic AI Workflow** powered by LangGraph
- **Real-time mutual fund data** from MFAPI.in
- **Natural language queries** about mutual funds
- **REST API** for easy integration
- **OpenAI integration** for intelligent responses

## Getting Started

### Prerequisites

- Python 3.9+
- OpenAI API key (or compatible mock)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/agentic-mfapi-ai.git
cd agentic-mfapi-ai
```

2. Set up a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and other configurations
```

### Running the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000.

### API Documentation

Once the application is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

- `GET /funds/search?q=bluechip` - Search for mutual funds by name
- `GET /funds/{scheme_code}` - Get details of a specific fund
- `POST /funds/compare` - Compare multiple funds
- `POST /ai/query` - Ask natural language questions about funds

### Example Query

Request:
```json
POST /ai/query
{
  "question": "Compare SBI Bluechip with ICICI Bluechip fund"
}
```

Response:
```json
{
  "summary": "SBI Bluechip has performed better over 3 years, while ICICI has had steadier NAV returns..."
}
```

## Running Tests

```bash
pytest
```

## Project Structure

```
agentic-mfapi-ai/
├── app/
│   ├── agents/                  # LangGraph agents
│   ├── api/                     # FastAPI routes
│   ├── services/                # mfapi wrappers
│   ├── schemas/                 # Pydantic models
│   ├── core/                    # Configs, LLM client
│   └── main.py                  # FastAPI entrypoint
├── tests/
├── README.md
├── requirements.txt
└── .env
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
