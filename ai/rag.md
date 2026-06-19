
# RAG Architecture Diagram

Create an architecture diagram:
Cloud architecture for a service that can take PDF files and allow users to have AI chat sessions regarding the content of the PDF files.

- Vectorize the PDF files using OpenAI's Embedding API
- Store them on a cloud vector database
- store the text chunks in a separate storage.

During a chat session, when a user asks a question
- turn the question in to a vector using OpenAI's embedding API
- query the vector database
- Use query result vectors to retrieve the associated text chunks.
- Query OpenAI's chat API with the retrieved text chunks and the original user question
- Return results from OpenAI's chat API to the user. Use AWS and OpenAI infrastructure where applicable.


```mermaid
graph TD
    %% Define Styles and Nodes
    subgraph Client Layer
        User[User / Client UI]
    end

    subgraph AWS Cloud Infrastructure
        %% API Gateway & Compute
        API_GW[Amazon API Gateway]
        Lambda_Ingest[AWS Lambda: Ingestion Worker]
        Lambda_Chat[AWS Lambda: Chat Execution Worker]

        %% Core Storage
        S3_PDF[Amazon S3: PDF File Bucket]
        S3_Chunks[Amazon S3 / DynamoDB: Text Chunks Storage]

        %% Vector Database
        OpenSearch[Amazon OpenSearch Serverless: Vector DB]
    end

    subgraph OpenAI Managed Infrastructure
        Embed_API[OpenAI Embedding API: text-embedding-3-small]
        Chat_API[OpenAI Chat Completion API: gpt-4o]
    end

    %% Flow 1: PDF Ingestion & Embedding Pipeline
    User -->|1. Upload PDF| API_GW
    API_GW -->|2. Save Raw File| S3_PDF
    S3_PDF -->|3. Trigger File Processing| Lambda_Ingest
    Lambda_Ingest -->|4. Parse & Extract Text Chunks| Lambda_Ingest
    Lambda_Ingest -->|5. Send Chunks for Vectorization| Embed_API
    Embed_API -->|6. Return Vector Dimensions| Lambda_Ingest
    Lambda_Ingest -->|7. Store Metadata + Original Text Chunks| S3_Chunks
    Lambda_Ingest -->|8. Index Vector Vectors mapped to Chunk IDs| OpenSearch

    %% Flow 2: Live Chat Session & Query Pipeline
    User -->|9. Submit Chat Question| API_GW
    API_GW -->|10. Execute Query Orchestration| Lambda_Chat
    Lambda_Chat -->|11. Convert Question to Embedding Vector| Embed_API
    Embed_API -->|12. Return Question Vector| Lambda_Chat
    Lambda_Chat -->|13. K-NN Vector Similarity Search| OpenSearch
    OpenSearch -->|14. Return Matching Chunk IDs| Lambda_Chat
    Lambda_Chat -->|15. Fetch Raw Associated Text Chunks| S3_Chunks
    S3_Chunks -->|16. Return Context Text Data| Lambda_Chat
    Lambda_Chat -->|17. Post Prompt Context + Original Question| Chat_API
    Chat_API -->|18. Return Generated Answer| Lambda_Chat
    Lambda_Chat -->|19. Stream Final Answer back to Client| User

    %% Highlighting Subgraphs
    style AWS Cloud Infrastructure fill:#f9f,stroke:#333,stroke-width:2px;
    style OpenAI Managed Infrastructure fill:#bbf,stroke:#333,stroke-width:2px;
```
