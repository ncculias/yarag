# YARAG (Yet Another RAG)

> [!Important]
    Work in progress (WIP). Do not expose any endpoints or deploy to production.

YARAG is a Retrieval-Augmented Generation (RAG) demonstration powered by FastAPI, Cloudflare R2, and Cloudflare AI Search.

Our core architecture is built around Cloudflare AI Search, which automatically monitors, ingests, and indexes files from our R2 bucket to enable instant vector-based chat interactions.

Because Cloudflare handles the entire RAG pipeline (storage, indexing, and retrieval) out of the box, our main task is simply to implement authentication and user management.

## Current Architecture

1. **Request URL**: The frontend sends a request to the FastAPI backend.
2. **Issue Presigned URL**: FastAPI validates the content type and generates a Cloudflare R2 presigned URL (S3-compatible).
3. **Direct Upload**: The frontend uploads the file directly to Cloudflare R2 using the presigned URL.
4. **Auto-Indexing**: Cloudflare AI Search automatically monitors the R2 bucket, processes incoming documents, and maintains the vector index.
5. **Chat Interface**: Users interact with the document collection using Cloudflare's conversational AI endpoints.

## 📝 TODOs

* [ ] **Authentication & Authorization**: Integrate user authentication within FastAPI endpoints.
* [ ] **AI Search Chat Proxy**: Implement a dedicated FastAPI endpoint wrapper that proxies conversational queries directly to Cloudflare AI Search.
* [ ] **Frontend Application**: Build a clean user interface to facilitate seamless file uploads and interactive chat experiences.

## Prerequisites

Before running the application, you need to configure your Cloudflare environment.

### 1. Create a Cloudflare R2 Bucket

Set up an object storage bucket to host your uploaded documents.

* Follow the official guide: [Cloudflare R2 - Create a Bucket](https://developers.cloudflare.com/r2/get-started/cli/#1-create-a-bucket)

### 2. Create a Cloudflare AI Search Instance

Provision an AI Search instance and bind it directly to your newly created R2 bucket. This enables automatic background document processing and indexing.

* Follow the official guide: [Cloudflare AI Search - Get Started](https://developers.cloudflare.com/ai-search/get-started/wrangler/#2-create-an-ai-search-instance)

## Installation

Clone the repository and create a environment file.

```bash
cd .env.example .env
```

### Running the Application

Start the FastAPI development server with hot-reload enabled:

```bash
uv run dev
```

The server will spin up, exposing API at: `http://127.0.0.1:8000`

---

## API Endpoints

### Generate Upload URL

Generates a secure presigned URL for direct object uploading.

* **URL**: `/api/v1/uploads`
* **Method**: `POST`
* **Status Code**: `201 Created`
* **Supported Content Types**: `text/plain`, `application/pdf`

#### Request Payload Example (`UploadRequest`)

```json
{
  "content_type": "application/pdf"
}
```

#### Response Payload Example (`UploadResponse`)

```json
{
  "key": "2026/06/25/e4a1b632fa1d4f29bc56bc9db85a11c2.pdf",
  "upload_url": "https://<account-id>.r2.cloudflarestorage.com/...",
  "expires_in": 3600,
  "required_headers": {
    "Content-Type": "application/pdf"
  }
}
```
