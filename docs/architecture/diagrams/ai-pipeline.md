# AI Pipeline

```mermaid
flowchart LR

A[User Query]

B[Embedding Generation]

C[Vector Search]

D[Retrieve Context]

E[Prompt Assembly]

F[LLM]

G[Citations]

H[Response]

A --> B

B --> C

C --> D

D --> E

E --> F

F --> G

G --> H
```