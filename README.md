# FinBot: RAG + RBAC Intelligent Finance Chatbot

FinBot is a full-stack, containerized intelligent finance chatbot built with Retrieval-Augmented Generation (RAG) and Role-Based Access Control (RBAC). It leverages state-of-the-art LLMs, semantic routing, and a vector database to provide accurate and secure answers to financial queries.

## 🌟 Features

- **Retrieval-Augmented Generation (RAG)**: Retrieves relevant context from financial documents using Qdrant vector database and LangChain.
- **Role-Based Access Control (RBAC)**: Secure access using JWT authentication. Ensures users only access data and features they have permission for.
- **Multi-LLM Support**: Configurable to use OpenAI and Groq (Llama 3) models.
- **Advanced Document Parsing**: Uses Docling for high-quality document ingestion.
- **Semantic Routing**: Intelligent query routing for fast and precise handling of user requests.
- **Modern Tech Stack**: FastAPI (Backend) and Next.js (Frontend).
- **Dockerized Setup**: Easy to run and deploy with Docker Compose.

## 🛠️ Technology Stack

- **Backend**: FastAPI, Python 3.11+
- **Frontend**: Next.js 14, React
- **Vector Database**: Qdrant
- **LLM & Embeddings**: LangChain, OpenAI, Groq, Sentence Transformers
- **Routing & Evaluation**: Semantic Router, Ragas
- **Containerization**: Docker & Docker Compose

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose
- API Keys for OpenAI and/or Groq

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/finbot.git
cd finbot
```

### 2. Environment Setup

Create a `.env` file in the root directory and configure your variables based on `.env.example`:

```bash
cp .env.example .env
```

Ensure you add your `OPENAI_API_KEY` and `GROQ_API_KEY`.

### 3. Running with Docker (Recommended)

The easiest way to run FinBot is using Docker Compose, which sets up the frontend, backend, and Qdrant database automatically.

```bash
docker-compose up --build
```

The services will be available at:
- **Frontend App**: [http://localhost:3000](http://localhost:3000)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Qdrant Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

### 4. Local Development (Without Docker)

If you prefer to run the services individually without Docker Compose:

**Start Qdrant**:
```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

**Run Backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
# Run the FastAPI server
uvicorn src.main:app --reload
```

**Run Frontend**:
```bash
cd frontend
npm install
npm run dev
```

## 📁 Project Structure

- `/backend` - FastAPI server, RAG pipelines, authentication, and core bot logic.
- `/frontend` - Next.js React application for the chat interface.
- `/data` - Directory for storing raw financial documents to be ingested.
- `/evaluation` - Scripts and notebooks for evaluating the RAG pipeline using Ragas.
- `/plan` - Project planning and architecture documents.
- `docker-compose.yml` - Configuration for multi-container Docker applications.

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.
