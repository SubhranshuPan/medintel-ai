# System Architecture

```mermaid
flowchart TD

A[React Frontend]

B[FastAPI Backend]

C[Authentication]

D[Chat]

E[RAG Engine]

F[(PostgreSQL)]

G[(Qdrant)]

H[LLM Providers]

A --> B

B --> C

B --> D

B --> E

C --> F

D --> F

E --> G

E --> H
```