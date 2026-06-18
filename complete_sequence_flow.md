# 1. Authentication & Account Management

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend UI
    participant API as API Gateway
    participant Auth as Auth Service
    participant DB as PostgreSQL
    participant JWT as JWT Manager

    User->>UI: Sign Up / Login
    UI->>API: Authentication Request
    API->>Auth: Validate Credentials

    alt New User
        Auth->>DB: Create User
        DB-->>Auth: User Created
        Auth-->>UI: Verification Required
        User->>UI: Verify Email
        UI->>Auth: Verification Token
        Auth->>DB: Mark Verified
    else Existing User
        Auth->>DB: Fetch User
        DB-->>Auth: User Record
    end

    Auth->>JWT: Generate Access Token
    JWT-->>Auth: JWT Token

    Auth-->>API: Authenticated
    API-->>UI: JWT + User Profile

    User->>UI: Access Protected Resource
    UI->>API: Request + JWT
    API->>JWT: Validate Token
    JWT-->>API: Valid
    API-->>UI: Authorized Response
```

---

# 2. Onboarding Flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend UI
    participant API as Core API
    participant DB as PostgreSQL
    participant LLM as LLM Provider Service

    User->>UI: First Login

    UI->>API: Start Onboarding
    API-->>UI: Onboarding Wizard

    User->>UI: Create Workspace
    UI->>API: Workspace Details
    API->>DB: Create Workspace

    User->>UI: Select Use Case
    UI->>API: Use Case Selection
    API->>DB: Save Preferences

    User->>UI: Connect LLM Provider
    UI->>API: Provider + API Key
    API->>LLM: Validate API Key
    LLM-->>API: Valid

    API->>DB: Store Encrypted Key

    User->>UI: Select Template
    UI->>API: Template Selection
    API->>DB: Create Initial Agent

    API-->>UI: Onboarding Complete
    UI-->>User: Redirect to Dashboard
```

---

# 3. Dashboard

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend UI
    participant API as Core API
    participant DB as PostgreSQL
    participant Analytics as Analytics Service

    User->>UI: Open Dashboard

    UI->>API: Load Dashboard

    par Load Agents
        API->>DB: Fetch Agents
        DB-->>API: Agent List
    and Load Workflows
        API->>DB: Fetch Workflows
        DB-->>API: Workflow List
    and Load Deployments
        API->>DB: Fetch Deployments
        DB-->>API: Deployment List
    and Load Analytics
        API->>Analytics: Fetch Metrics
        Analytics-->>API: Usage Data
    end

    API-->>UI: Dashboard Data

    UI-->>User: Render Dashboard

    User->>UI: Create New Resource
    UI->>API: Create Request

    alt Agent
        API->>DB: Create Agent
    else Workflow
        API->>DB: Create Workflow
    else Multi-Agent System
        API->>DB: Create System
    end

    API-->>UI: Resource Created
    UI-->>User: Redirect to Builder
```
# 4. Single Agent Builder

```mermaid
sequenceDiagram
    actor User
    participant UI as Agent Builder UI
    participant API as Core API
    participant DB as PostgreSQL
    participant Runtime as Agent Runtime
    participant Vector as Vector DB
    participant Storage as S3 Storage

    User->>UI: Create / Open Agent
    UI->>API: Load Agent
    API->>DB: Fetch Agent Config
    DB-->>API: Agent Data
    API-->>UI: Builder Configuration

    User->>UI: Configure Identity
    User->>UI: Configure LLM
    User->>UI: Configure Prompt
    User->>UI: Configure Memory
    User->>UI: Configure Tools
    User->>UI: Configure Guardrails
    User->>UI: Configure Output

    UI->>API: Save Configuration
    API->>DB: Store Agent Config

    opt Knowledge Upload
        User->>UI: Upload Documents
        UI->>API: Upload Files
        API->>Storage: Store Files
        API->>Vector: Index Documents
    end

    opt Agent Versioning
        User->>UI: Create Version
        UI->>API: Save Snapshot
        API->>DB: Store Version
    end

    User->>UI: Open Playground
    User->>UI: Send Test Message

    UI->>API: Execute Agent
    API->>Runtime: Run Agent

    Runtime->>Vector: Retrieve Context
    Vector-->>Runtime: Relevant Chunks

    Runtime-->>API: Response + Tool Calls + Traces
    API-->>UI: Execution Result

    UI-->>User: Response
    UI-->>User: Token Usage
    UI-->>User: Tool Calls
    UI-->>User: Execution Trace

    opt Agent Management
        User->>UI: Rename / Duplicate / Archive / Delete
        UI->>API: Management Action
        API->>DB: Update Agent
    end
```

---

# 5. Knowledge Base Management

```mermaid
sequenceDiagram
    actor User
    participant UI as Knowledge Base UI
    participant API as KB Service
    participant Storage as S3 Storage
    participant Queue as Queue Worker
    participant Embed as Embedding Service
    participant Vector as Vector DB
    participant DB as PostgreSQL

    User->>UI: Create Knowledge Base
    UI->>API: Create KB
    API->>DB: Store KB

    alt Upload File
        User->>UI: Upload Document
        UI->>API: Upload File
        API->>Storage: Store File
        API->>Queue: Trigger Indexing
        Queue->>Embed: Generate Embeddings
        Embed->>Vector: Store Vectors
        Queue->>DB: Update Status
    end

    alt Connect URL
        User->>UI: Add URL
        UI->>API: Submit URL
        API->>Queue: Crawl URL
        Queue->>Embed: Process Content
        Embed->>Vector: Store Vectors
    end

    alt Connect Notion
        User->>UI: Connect Workspace
        UI->>API: Authorize Notion
        API->>Queue: Sync Pages
        Queue->>Embed: Process Content
        Embed->>Vector: Store Vectors
    end

    User->>UI: Search KB
    UI->>API: Search Query
    API->>Vector: Semantic Search
    Vector-->>API: Results
    API-->>UI: Search Results

    opt Reindex KB
        User->>UI: Reindex
        UI->>API: Reindex Request
        API->>Queue: Reindex Job
    end

    opt Delete Document
        User->>UI: Delete File
        UI->>API: Delete Request
        API->>Storage: Remove File
        API->>Vector: Remove Embeddings
        API->>DB: Update Records
    end
```

---

# 6. Tool Management

```mermaid
sequenceDiagram
    actor User
    participant UI as Tool Management UI
    participant API as Tool Service
    participant Registry as Tool Registry
    participant MCP as MCP Connector
    participant External as External APIs
    participant DB as PostgreSQL

    User->>UI: Open Tool Marketplace
    UI->>API: Load Tools
    API->>Registry: Fetch Available Tools
    Registry-->>API: Tool List
    API-->>UI: Available Tools

    User->>UI: Add Tool
    UI->>API: Enable Tool
    API->>DB: Save Tool Config

    opt Configure Tool
        User->>UI: Update Settings
        UI->>API: Save Configuration
        API->>DB: Update Tool Config
    end

    opt Test Tool
        User->>UI: Run Test
        UI->>API: Execute Tool
        API->>External: Call API
        External-->>API: Result
        API-->>UI: Test Output
    end

    opt Create Custom API Tool
        User->>UI: Define Endpoint
        UI->>API: Create Tool
        API->>Registry: Register Tool
        API->>DB: Store Tool Definition
    end

    opt Connect MCP Server
        User->>UI: Add MCP Endpoint
        UI->>API: Connect MCP
        API->>MCP: Validate Connection
        MCP-->>API: Available Resources
        API->>DB: Save MCP Config
        API-->>UI: MCP Connected
    end

    User->>UI: Browse Connected Tools
    UI->>API: Load User Tools
    API->>DB: Fetch Configurations
    DB-->>API: Tool Records
    API-->>UI: Tool Dashboard
```
# 7. Multi-Agent Builder

```mermaid
sequenceDiagram
    actor User
    participant UI as Multi-Agent Builder UI
    participant API as Multi-Agent Service
    participant DB as PostgreSQL
    participant Orch as Orchestrator
    participant Bus as A2A / Message Bus
    participant Memory as Shared Memory
    participant AgentA as Research Agent
    participant AgentB as Writer Agent
    participant AgentC as Reviewer Agent

    User->>UI: Create Multi-Agent System
    UI->>API: Create System
    API->>DB: Store System

    User->>UI: Add Agent Nodes
    User->>UI: Connect Agents
    User->>UI: Configure Communication
    User->>UI: Select Pattern

    alt Supervisor Pattern
        UI->>API: Supervisor Configuration
    else Sequential Pattern
        UI->>API: Sequential Configuration
    else Swarm Pattern
        UI->>API: Swarm Configuration
    end

    User->>UI: Configure Shared Memory
    UI->>API: Shared Memory Settings
    API->>Memory: Create Shared Context

    User->>UI: Configure Shared Tools
    UI->>API: Tool Assignments

    User->>UI: Run Multi-Agent System

    UI->>API: Execute System
    API->>Orch: Start Orchestration

    Orch->>Bus: Initialize Communication Bus

    Note over Orch,AgentC: Supervisor Pattern Example

    Orch->>AgentA: Research Task
    AgentA-->>Bus: Findings

    Orch->>AgentB: Draft Content
    AgentB-->>Bus: Draft

    Orch->>AgentC: Review Draft
    AgentC-->>Bus: Review

    Bus->>Memory: Update Shared State

    Orch->>Memory: Read Shared Context
    Memory-->>Orch: Aggregated Results

    Orch-->>API: Final Output

    API-->>UI: Results
    UI-->>User: Execution Graph
    UI-->>User: Inter-Agent Messages
    UI-->>User: Final Response
```

---

# 8. Workflow Builder

```mermaid
sequenceDiagram
    actor User
    participant UI as Workflow Builder UI
    participant API as Workflow Service
    participant DB as PostgreSQL
    participant Engine as Workflow Engine
    participant Queue as Celery/ARQ
    participant Agent as Agent Runtime
    participant Tool as Tool Executor
    participant External as External API
    participant Human as Human Approver

    User->>UI: Create Workflow
    UI->>API: Create Workflow
    API->>DB: Store Workflow

    User->>UI: Drag & Drop Nodes
    User->>UI: Connect Nodes
    User->>UI: Configure Edges

    User->>UI: Configure Trigger Node
    User->>UI: Configure Agent Node
    User->>UI: Configure Tool Node
    User->>UI: Configure API Node
    User->>UI: Configure Condition Node
    User->>UI: Configure Approval Node

    UI->>API: Save Workflow DAG
    API->>DB: Store DAG Definition

    User->>UI: Run Workflow

    UI->>API: Execute Workflow
    API->>Queue: Queue Workflow Run

    Queue->>Engine: Start Execution

    Note over Engine: Trigger Node

    Engine->>Agent: Execute Agent Node
    Agent-->>Engine: Agent Output

    Engine->>Tool: Execute Tool Node
    Tool-->>Engine: Tool Output

    Engine->>External: Execute API Node
    External-->>Engine: API Response

    Engine->>Engine: Evaluate Condition Node

    alt Human Approval Required
        Engine->>Human: Approval Request
        Human-->>Engine: Approve / Reject
    end

    Engine->>DB: Store Node Outputs
    Engine->>DB: Store Run Logs

    Engine-->>API: Workflow Result
    API-->>UI: Execution Results

    UI-->>User: Workflow Run
    UI-->>User: Node Outputs
    UI-->>User: Execution Logs
```

---

# 9. Deployment Center

```mermaid
sequenceDiagram
    actor User
    participant UI as Deployment Center
    participant API as Deployment Service
    participant DB as PostgreSQL
    participant Gateway as API Gateway
    participant Widget as Widget Service
    participant Webhook as Webhook Service

    User->>UI: Select Agent / Workflow

    alt Deploy Agent
        User->>UI: Deploy Agent
        UI->>API: Deployment Request
        API->>DB: Create Deployment Record
        API->>Gateway: Generate API Endpoint
        Gateway-->>API: Endpoint URL
        API-->>UI: Deployment Successful
    else Deploy Workflow
        User->>UI: Deploy Workflow
        UI->>API: Deployment Request
        API->>DB: Create Workflow Deployment
        API->>Gateway: Register Endpoint
    end

    opt Generate API
        User->>UI: Generate API Key
        UI->>API: API Request
        API->>DB: Store API Credentials
        API-->>UI: API Endpoint + Key
    end

    opt Generate Widget
        User->>UI: Generate Widget
        UI->>API: Widget Request
        API->>Widget: Build Widget Config
        Widget-->>API: Embed Script
        API-->>UI: Widget Code
    end

    opt Generate Webhook
        User->>UI: Configure Webhook
        UI->>API: Webhook Setup
        API->>Webhook: Register Webhook
        Webhook-->>API: Webhook URL
        API-->>UI: Webhook Details
    end

    opt Revoke Deployment
        User->>UI: Disable Deployment
        UI->>API: Revoke Request
        API->>Gateway: Disable Endpoint
        API->>DB: Mark Deployment Inactive
        API-->>UI: Deployment Revoked
    end
```

---

# Advanced Multi-Agent Runtime Flow (Actual Execution Architecture)

```mermaid
sequenceDiagram
    actor User

    participant Orch as Orchestrator
    participant Planner as Planner Agent
    participant Research as Research Agent
    participant Writer as Writer Agent
    participant Reviewer as Reviewer Agent

    participant Memory as Shared Memory
    participant Bus as A2A Bus

    User->>Orch: Goal

    Orch->>Planner: Break Task

    Planner-->>Orch: Sub Tasks

    Orch->>Research: Research Topic
    Research->>Memory: Store Findings
    Research-->>Bus: Findings

    Orch->>Writer: Generate Draft
    Writer->>Memory: Read Findings
    Writer-->>Bus: Draft

    Orch->>Reviewer: Review Draft
    Reviewer->>Memory: Read Draft
    Reviewer-->>Bus: Review Notes

    Orch->>Memory: Read Shared State

    Memory-->>Orch: Consolidated Context

    Orch-->>User: Final Output
```

---

# Advanced Workflow Runtime Flow (Actual DAG Execution)

```mermaid
sequenceDiagram
    actor User
    participant Trigger as Trigger Node
    participant Engine as Workflow Engine
    participant Agent as Agent Node
    participant Tool as Tool Node
    participant API as API Node
    participant Cond as Condition Node
    participant Human as Approval Node
    participant Finish as End Node

    User->>Trigger: Start Workflow

    Trigger->>Engine: Trigger Payload

    Engine->>Agent: Execute Agent
    Agent-->>Engine: Response

    Engine->>Tool: Execute Tool
    Tool-->>Engine: Tool Result

    Engine->>API: Call External API
    API-->>Engine: API Response

    Engine->>Cond: Evaluate Logic

    alt Condition True
        Cond->>Human: Request Approval
        Human-->>Cond: Approved
    else Condition False
        Cond-->>Engine: Continue
    end

    Cond->>Finish: Final Payload
    Finish-->>User: Workflow Result
