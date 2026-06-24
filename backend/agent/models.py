"""
=============================================================================
AI Agent Platform — CreateAgentRequest Schema
=============================================================================
Author  : Senior Backend Architect
Version : 1.0.0
Python  : 3.11+
Pydantic: v2.x

Design Philosophy
-----------------
• Every section is its own BaseModel → composable, independently versionable,
  and reusable across UpdateAgentRequest, CloneAgentRequest, etc.
• Literals + Unions replace magic strings → IDE-completable, self-documenting.
• `model_config = ConfigDict(...)` replaces the old inner `class Config`.
• All free-form extension points use `extra_config: dict[str, Any]` rather
  than `model_config extra="allow"` to keep the surface area explicit.
• Fields carry `description=` for OpenAPI docs auto-generation.
• Validators (`@field_validator`, `@model_validator`) enforce cross-field rules
  at parse time, not at runtime deep in business logic.
=============================================================================
"""

from __future__ import annotations

import re
import uuid
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    UUID4,
)


# ---------------------------------------------------------------------------
# Shared / Primitive Types
# ---------------------------------------------------------------------------

AgentId       = Annotated[UUID4, Field(description="Agent's UUID (server-assigned, ignored on create).")]
SlugStr       = Annotated[str,   Field(min_length=2, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
SemVerStr     = Annotated[str,   Field(pattern=r"^\d+\.\d+\.\d+$", description="Semantic version string, e.g. '1.0.0'.")]
PositiveFloat = Annotated[float, Field(gt=0)]
ZeroToOne     = Annotated[float, Field(ge=0.0, le=1.0)]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AgentVisibility(str, Enum):
    PRIVATE    = "private"       # Only owner
    WORKSPACE  = "workspace"     # All workspace members
    PUBLIC     = "public"        # Listed in marketplace


class LLMProvider(str, Enum):
    OPENAI     = "openai"
    ANTHROPIC  = "anthropic"
    GOOGLE     = "google"
    MISTRAL    = "mistral"
    GROQ       = "groq"
    OLLAMA     = "ollama"        # Self-hosted
    AZURE      = "azure_openai"
    BEDROCK    = "aws_bedrock"
    CUSTOM     = "custom"        # Bring-your-own endpoint


class MemoryBackend(str, Enum):
    NONE       = "none"
    IN_PROCESS = "in_process"    # Ephemeral per-session dict
    REDIS      = "redis"
    POSTGRES   = "postgres"
    PINECONE   = "pinecone"
    WEAVIATE   = "weaviate"
    QDRANT     = "qdrant"
    CHROMA     = "chroma"
    MILVUS     = "milvus"


class EmbeddingProvider(str, Enum):
    OPENAI     = "openai"
    COHERE     = "cohere"
    HUGGINGFACE= "huggingface"
    GOOGLE     = "google"
    CUSTOM     = "custom"


class ToolType(str, Enum):
    BUILTIN    = "builtin"       # Platform-provided tools
    OPENAPI    = "openapi"       # Auto-generated from OpenAPI spec
    MCP        = "mcp"           # Model Context Protocol server
    FUNCTION   = "function"      # Inline Python / JS function
    A2A        = "a2a"           # Agent-to-Agent call
    WORKFLOW   = "workflow"      # Trigger a workflow node


class GuardrailAction(str, Enum):
    BLOCK      = "block"         # Reject the message outright
    WARN       = "warn"          # Pass through but log
    REDACT     = "redact"        # Mask sensitive content
    REWRITE    = "rewrite"       # Use LLM to rephrase


class OutputFormat(str, Enum):
    TEXT       = "text"
    MARKDOWN   = "markdown"
    JSON       = "json"
    JSONL      = "jsonl"
    XML        = "xml"
    YAML       = "yaml"
    CUSTOM     = "custom"


class WorkflowTrigger(str, Enum):
    MANUAL     = "manual"
    WEBHOOK    = "webhook"
    CRON       = "cron"
    EVENT      = "event"


# ============================================================================
# SECTION 1 — Identity
# ============================================================================

class AvatarConfig(BaseModel):
    """Visual identity of the agent."""
    model_config = ConfigDict(str_strip_whitespace=True)

    url:        AnyHttpUrl | None = Field(None, description="Hosted image URL.")
    emoji:      str | None        = Field(None, max_length=2, description="Single emoji fallback.")
    bg_color:   str | None        = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex colour for avatar background.")


class IdentityConfig(BaseModel):
    """
    Public-facing identity of the agent.
    Slug is enforced as lowercase-kebab-case for stable URL routing
    (e.g. /agents/my-sales-bot) independent of the display name.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    name:         str             = Field(..., min_length=2, max_length=120, description="Display name shown in the UI.")
    slug:         SlugStr         = Field(..., description="URL-safe unique identifier within a workspace.")
    description:  str | None      = Field(None, max_length=1000, description="Short purpose statement shown in agent listings.")
    tags:         list[str]       = Field(default_factory=list, max_length=20, description="Free-form tags for search / filtering.")
    avatar:       AvatarConfig    = Field(default_factory=AvatarConfig)
    visibility:   AgentVisibility = Field(AgentVisibility.PRIVATE)
    version:      SemVerStr       = Field("1.0.0", description="Schema version of THIS agent config, not the platform version.")

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, v: list[str]) -> list[str]:
        """Lowercase, strip, deduplicate tags."""
        return list({t.lower().strip() for t in v if t.strip()})


# ============================================================================
# SECTION 2 — LLM Configuration
# ============================================================================

class LLMRetryPolicy(BaseModel):
    max_attempts:    int           = Field(3,    ge=1, le=10)
    backoff_seconds: float         = Field(1.0,  ge=0.1, le=60.0)
    retry_on:        list[str]     = Field(
        default_factory=lambda: ["rate_limit_error", "server_error"],
        description="Error codes / types that trigger a retry.",
    )


class FallbackLLMConfig(BaseModel):
    """
    Secondary model used when the primary exceeds its quota or errors out.
    Mirrors a subset of LLMConfig fields (no nested fallback to avoid cycles).
    """
    provider:    LLMProvider  = Field(...)
    model_id:    str          = Field(..., description="Provider-specific model identifier.")
    temperature: ZeroToOne    = Field(0.7)
    max_tokens:  int          = Field(2048, ge=1, le=200_000)


class LLMConfig(BaseModel):
    """
    Everything needed to call a language model.

    Design decisions
    ----------------
    • `model_id` is a raw string (not an Enum) because providers release new
      models constantly; hardcoding would require schema migrations.
    • `credentials_ref` stores the SECRET NAME (e.g. 'OPENAI_KEY') not the
      key itself.  The platform resolves it at runtime from a secrets vault.
    • `extra_params` lets providers add exotic knobs (e.g. Anthropic's
      `thinking`, OpenAI's `response_format`) without schema churn.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    provider:         LLMProvider         = Field(...)
    model_id:         str                 = Field(..., description="e.g. 'gpt-4o', 'claude-sonnet-4-6', 'gemini-2.0-flash'.")
    credentials_ref:  str | None          = Field(None, description="Secret-store key name for the API key.")
    base_url:         AnyHttpUrl | None   = Field(None, description="Custom endpoint for OLLAMA / Azure / proxy.")
    api_version:      str | None          = Field(None, description="Required for Azure OpenAI.")

    # Sampling
    temperature:      ZeroToOne           = Field(0.7)
    top_p:            ZeroToOne | None    = Field(None, description="Nucleus sampling threshold.")
    top_k:            int | None          = Field(None, ge=1, description="Top-K sampling (Anthropic / Google).")
    max_tokens:       int                 = Field(2048, ge=1, le=200_000)
    max_input_tokens: int | None          = Field(None, ge=1, description="Hard cap on context window input.")
    stop_sequences:   list[str]           = Field(default_factory=list, max_length=8)
    seed:             int | None          = Field(None, description="For reproducible outputs in testing.")
    stream:           bool                = Field(False, description="Enable token-by-token streaming.")

    # Cost & latency controls
    timeout_seconds:  PositiveFloat       = Field(60.0)
    retry_policy:     LLMRetryPolicy      = Field(default_factory=LLMRetryPolicy)
    fallback:         FallbackLLMConfig | None = Field(None)

    # Escape hatch for provider-specific params
    extra_params:     dict[str, Any]      = Field(default_factory=dict, description="Forwarded verbatim to the provider SDK.")

    @model_validator(mode="after")
    def azure_requires_api_version(self) -> "LLMConfig":
        if self.provider == LLMProvider.AZURE and not self.api_version:
            raise ValueError("api_version is required for provider=azure_openai.")
        return self


# ============================================================================
# SECTION 3 — Prompt Configuration
# ============================================================================

class MessageRole(str, Enum):
    SYSTEM    = "system"
    HUMAN     = "human"
    ASSISTANT = "assistant"


class FewShotExample(BaseModel):
    """
    A single input/output demonstration injected before the conversation.
    Using explicit role fields rather than a flat list keeps it readable
    and avoids off-by-one errors in alternating role sequences.
    """
    input:    str = Field(..., min_length=1)
    output:   str = Field(..., min_length=1)
    rationale: str | None = Field(None, description="Optional chain-of-thought explanation (for training data).")


class PromptVariable(BaseModel):
    """
    Declared template variables resolved at runtime.
    Declaring them explicitly (rather than scanning the template with regex)
    enables the UI to render a variable-binding form.
    """
    name:         str        = Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description:  str | None = Field(None)
    default:      Any        = Field(None)
    required:     bool       = Field(True)


class PromptConfig(BaseModel):
    """
    Prompt engineering configuration.

    `system_prompt` is the authoritative instruction layer.
    `human_prefix` / `ai_prefix` allow persona-level role renaming
    (e.g. "User" → "Customer", "Assistant" → "Aria").
    `few_shot_examples` are injected BEFORE the live conversation turns.
    `chain_of_thought` adds "Think step by step" style reasoning instructions.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    system_prompt:      str                  = Field(..., min_length=10, description="Core instruction set for the agent.")
    human_prefix:       str                  = Field("Human",    max_length=50)
    ai_prefix:          str                  = Field("Assistant",max_length=50)
    few_shot_examples:  list[FewShotExample] = Field(default_factory=list, max_length=20)
    variables:          list[PromptVariable] = Field(default_factory=list)
    chain_of_thought:   bool                 = Field(False, description="Inject CoT reasoning instructions automatically.")
    language:           str                  = Field("en", description="BCP-47 language code. Agent replies in this language.")

    @field_validator("system_prompt")
    @classmethod
    def no_injection_patterns(cls, v: str) -> str:
        """Rudimentary check — real prompt injection detection runs server-side."""
        forbidden = ["ignore previous instructions", "disregard all prior"]
        for pattern in forbidden:
            if pattern.lower() in v.lower():
                raise ValueError(f"System prompt contains a forbidden pattern: '{pattern}'.")
        return v


# ============================================================================
# SECTION 4 — Memory Configuration
# ============================================================================

class EmbeddingConfig(BaseModel):
    provider:   EmbeddingProvider = Field(EmbeddingProvider.OPENAI)
    model_id:   str               = Field("text-embedding-3-small")
    dimensions: int               = Field(1536, ge=64, le=4096)
    batch_size: int               = Field(100,  ge=1,  le=2048)


class ShortTermMemoryConfig(BaseModel):
    """
    Sliding window / token-budget conversation buffer.
    Controls how much of the live conversation the agent holds in its context.
    `strategy` determines eviction behaviour when the window is full.
    """
    enabled:          bool    = Field(True)
    window_size:      int     = Field(20,   ge=1,  le=200,  description="Number of message turns to retain.")
    max_token_budget: int     = Field(8000, ge=256,         description="Token ceiling for the entire context window.")
    strategy:         Literal["sliding_window", "token_budget", "summarise"] = Field("sliding_window")


# NOTE: LongTermMemoryConfig has been intentionally removed from this schema.
#
# Long-term memory is a PLATFORM-LEVEL concern managed by the external memory
# layer. Every agent automatically gets persistent LTM — the user has no
# configuration surface here. Platform-internal LTM settings (backend, TTL,
# namespace, embeddings, similarity thresholds) are managed via the Memory
# Service's own admin config, not per-agent request payloads.
#
# This keeps the CreateAgentRequest honest about what the user actually owns.


class RAGConfig(BaseModel):
    """
    Retrieval-Augmented Generation — links static knowledge bases to the agent.

    RAG stays user-configurable because it answers: "which domain knowledge
    should this agent be able to look up?" — a genuine per-agent design choice.
    This is READ-ONLY retrieval from pre-ingested KBs; it does not write to
    memory. The platform's external LTM layer handles dynamic memory writes.
    """
    enabled:              bool            = Field(False)
    knowledge_base_ids:   list[uuid.UUID] = Field(
        default_factory=list,
        description="UUIDs of platform-managed knowledge bases to attach to this agent.",
    )
    top_k:                int             = Field(5, ge=1, le=50, description="Documents retrieved per query.")
    similarity_threshold: ZeroToOne       = Field(0.70, description="Minimum cosine similarity to include a result.")
    reranker_enabled:     bool            = Field(False, description="Apply a cross-encoder reranker after retrieval.")
    citation_mode:        Literal["none", "inline", "footnote"] = Field("inline")
    embedding:            EmbeddingConfig = Field(
        default_factory=EmbeddingConfig,
        description="Embedding model used at QUERY time. Must match the model used during KB ingestion.",
    )


class MemoryConfig(BaseModel):
    """
    User-facing memory configuration.

    short_term  → In-context conversation window (user-configurable).
    rag         → Static knowledge base retrieval (user-configurable).
    long_term   → Persistent per-user memory (platform-managed, not exposed here).
    """
    short_term: ShortTermMemoryConfig = Field(default_factory=ShortTermMemoryConfig)
    rag:        RAGConfig             = Field(default_factory=RAGConfig)


# ============================================================================
# SECTION 5 — Tools Configuration
# ============================================================================

class BuiltinToolConfig(BaseModel):
    """Platform-provided, zero-config tools."""
    tool_id:     str             = Field(..., description="e.g. 'web_search', 'code_interpreter', 'image_gen'.")
    enabled:     bool            = Field(True)
    settings:    dict[str, Any]  = Field(default_factory=dict, description="Tool-specific knobs.")


class OpenAPIToolConfig(BaseModel):
    """
    Auto-generates callable functions from an OpenAPI 3.x spec.
    The platform downloads the spec, parses operations, and registers
    each operation as a discrete tool function.
    """
    spec_url:         AnyHttpUrl       = Field(..., description="URL of the OpenAPI JSON/YAML spec.")
    credentials_ref:  str | None       = Field(None, description="API key / OAuth token secret name.")
    allowed_ops:      list[str]        = Field(default_factory=list, description="operationIds to expose. Empty = all.")
    denied_ops:       list[str]        = Field(default_factory=list, description="operationIds to hide.")
    timeout_seconds:  PositiveFloat    = Field(30.0)


class MCPServerConfig(BaseModel):
    """
    Model Context Protocol server registration.
    MCP is the emerging standard (Anthropic, 2024) for exposing tools,
    resources, and prompts to LLMs over a typed JSON-RPC interface.
    """
    server_id:        str              = Field(..., description="Stable internal name for this MCP server.")
    transport:        Literal["stdio", "sse", "websocket"] = Field("sse")
    endpoint:         AnyHttpUrl | None = Field(None, description="Remote URL (required for sse/websocket).")
    command:          list[str]        = Field(default_factory=list, description="CLI command for stdio transport.")
    credentials_ref:  str | None       = Field(None)
    allowed_tools:    list[str]        = Field(default_factory=list, description="Empty = expose all server tools.")
    auto_approve:     bool             = Field(False, description="Skip user confirmation for tool calls.")


class A2AConfig(BaseModel):
    """
    Agent-to-Agent communication spec.
    Follows the Google A2A draft specification (2025).
    Allows this agent to invoke other agents as if they were tools.
    """
    target_agent_id:  uuid.UUID        = Field(...)
    capability:       str              = Field(..., description="Declared capability name exposed by the target agent.")
    auth_mode:        Literal["platform_token", "api_key", "oauth2"] = Field("platform_token")
    credentials_ref:  str | None       = Field(None)
    timeout_seconds:  PositiveFloat    = Field(60.0)
    max_hops:         int              = Field(3, ge=1, le=10, description="Prevents infinite A2A recursion.")


class InlineFunctionConfig(BaseModel):
    """
    Sandboxed inline code executed as a tool.
    WARNING: always runs in an isolated sandbox (e.g. gVisor / Firecracker).
    """
    name:        str                = Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str                = Field(..., description="Natural-language description shown to the LLM.")
    runtime:     Literal["python3", "nodejs20"] = Field("python3")
    code:        str                = Field(..., min_length=10, description="Function source code.")
    input_schema:  dict[str, Any]   = Field(default_factory=dict, description="JSON Schema for function arguments.")
    output_schema: dict[str, Any]   = Field(default_factory=dict)
    timeout_ms:  int                = Field(5000, ge=100, le=30_000)
    memory_mb:   int                = Field(128, ge=32, le=1024)


class ToolEntry(BaseModel):
    """
    Discriminated union — every tool is ONE of these variants.
    Using `tool_type` as the discriminator means Pydantic resolves
    the correct model without ambiguous field overlap.
    """
    tool_type:  ToolType = Field(..., description="Discriminator field.")
    config: (
        BuiltinToolConfig
        | OpenAPIToolConfig
        | MCPServerConfig
        | A2AConfig
        | InlineFunctionConfig
    ) = Field(..., description="Tool-type-specific configuration.")

    @model_validator(mode="after")
    def validate_config_type(self) -> "ToolEntry":
        """Ensure config type matches tool_type discriminator."""
        type_map = {
            ToolType.BUILTIN:  BuiltinToolConfig,
            ToolType.OPENAPI:  OpenAPIToolConfig,
            ToolType.MCP:      MCPServerConfig,
            ToolType.A2A:      A2AConfig,
            ToolType.FUNCTION: InlineFunctionConfig,
        }
        expected = type_map.get(self.tool_type)
        if expected and not isinstance(self.config, expected):
            raise ValueError(f"tool_type='{self.tool_type}' requires config of type {expected.__name__}.")
        return self


class ToolsConfig(BaseModel):
    tools:                list[ToolEntry] = Field(default_factory=list)
    parallel_tool_calls:  bool            = Field(True,  description="Allow LLM to call multiple tools in a single turn.")
    max_tool_iterations:  int             = Field(10, ge=1, le=50, description="Prevent runaway agentic loops.")
    tool_choice:          Literal["auto", "none", "required"] = Field("auto")


# ============================================================================
# SECTION 6 — Guardrails Configuration
# ============================================================================

class ContentPolicy(BaseModel):
    """
    NLP-level content safety filter (PII, toxicity, topic adherence).
    `categories` maps a policy category to its enforcement action.
    """
    enabled:    bool                           = Field(True)
    categories: dict[str, GuardrailAction]     = Field(
        default_factory=lambda: {
            "pii":            GuardrailAction.REDACT,
            "toxic_language": GuardrailAction.BLOCK,
            "prompt_injection": GuardrailAction.BLOCK,
        },
        description="Map of policy category → enforcement action.",
    )
    custom_rules: list[str] = Field(default_factory=list, description="Regex patterns that trigger a BLOCK action.")


class TopicPolicy(BaseModel):
    """Keep the agent focused on its declared domain."""
    enabled:          bool        = Field(False)
    allowed_topics:   list[str]   = Field(default_factory=list, description="Agent ONLY discusses these topics.")
    denied_topics:    list[str]   = Field(default_factory=list, description="Agent NEVER discusses these topics.")
    off_topic_message: str        = Field(
        "I'm only able to help with topics related to my purpose.",
        description="Static response for off-topic requests.",
    )


class RateLimitPolicy(BaseModel):
    """Per-user abuse prevention."""
    enabled:             bool  = Field(True)
    requests_per_minute: int   = Field(20,    ge=1, le=1000)
    requests_per_day:    int   = Field(1000,  ge=1)
    max_input_tokens:    int   = Field(10_000, ge=1, description="Per-request input token ceiling.")


class HumanInTheLoopConfig(BaseModel):
    """
    Pause-and-confirm flows for high-stakes actions.
    When triggered, the agent halts and awaits human approval
    before executing the flagged tool call.
    """
    enabled:             bool       = Field(False)
    trigger_on_tools:    list[str]  = Field(default_factory=list, description="Tool IDs that require approval.")
    approval_timeout_s:  int        = Field(300, ge=30, le=86400, description="Seconds before the task auto-cancels.")
    notify_channels:     list[str]  = Field(default_factory=list, description="e.g. 'slack', 'email', 'webhook'.")


class GuardrailsConfig(BaseModel):
    content_policy:     ContentPolicy         = Field(default_factory=ContentPolicy)
    topic_policy:       TopicPolicy           = Field(default_factory=TopicPolicy)
    rate_limit:         RateLimitPolicy       = Field(default_factory=RateLimitPolicy)
    human_in_the_loop:  HumanInTheLoopConfig  = Field(default_factory=HumanInTheLoopConfig)


# ============================================================================
# SECTION 7 — Output Configuration
# ============================================================================

class JSONSchemaOutput(BaseModel):
    """Force the LLM to return JSON matching a specific schema (structured outputs)."""
    schema_def:  dict[str, Any] = Field(..., description="A valid JSON Schema object.")
    strict:      bool           = Field(True,  description="Use provider strict-mode where available (OpenAI, Anthropic).")


class StreamingConfig(BaseModel):
    enabled:          bool = Field(False)
    chunk_size_tokens: int = Field(1, ge=1, le=100, description="Tokens per streamed chunk (1 = word-by-word).")


class OutputConfig(BaseModel):
    """
    Controls what the agent returns and how it returns it.
    `json_schema` activates structured output — the LLM is constrained to
    produce JSON that passes schema validation before delivery.
    `post_processing` is a list of built-in transforms applied after generation
    (e.g. markdown → HTML, translate, summarise).
    """
    format:             OutputFormat           = Field(OutputFormat.MARKDOWN)
    json_schema:        JSONSchemaOutput | None = Field(None, description="Required when format=json.")
    streaming:          StreamingConfig        = Field(default_factory=StreamingConfig)
    max_response_tokens: int | None            = Field(None, ge=1, description="Overrides LLM max_tokens for this agent.")
    post_processing:    list[Literal["html_render", "translate", "summarise", "tts"]] = Field(default_factory=list)
    language:           str | None             = Field(None, description="Force response language (BCP-47). Overrides prompt.language.")

    @model_validator(mode="after")
    def json_schema_required_for_json_format(self) -> "OutputConfig":
        if self.format == OutputFormat.JSON and self.json_schema is None:
            raise ValueError("json_schema must be provided when format='json'.")
        return self


# ============================================================================
# SECTION 8 — Workflow / Orchestration (ADDITIONAL)
# ============================================================================

class CronTrigger(BaseModel):
    expression: str = Field(..., description="Standard cron expression, e.g. '0 9 * * 1-5'.")
    timezone:   str = Field("UTC", description="IANA timezone name.")


class WebhookTrigger(BaseModel):
    path:            str                   = Field(..., description="Platform-relative path, e.g. '/hooks/agent-xyz'.")
    secret_ref:      str | None            = Field(None, description="HMAC secret for signature validation.")
    allowed_methods: list[Literal["GET","POST","PUT"]] = Field(default_factory=lambda: ["POST"])


class WorkflowConfig(BaseModel):
    """
    Lets an agent act as an orchestrator or a step in a DAG.
    `workflow_id` links to a pre-built workflow definition (visual DAG editor).
    Keeps the agent config lean — workflow logic lives in the workflow service.
    """
    enabled:          bool                 = Field(False)
    workflow_id:      uuid.UUID | None     = Field(None, description="Links to a Workflow entity.")
    trigger:          WorkflowTrigger      = Field(WorkflowTrigger.MANUAL)
    cron:             CronTrigger | None   = Field(None)
    webhook:          WebhookTrigger | None = Field(None)
    input_mapping:    dict[str, str]       = Field(default_factory=dict, description="Maps workflow inputs to agent variables.")
    output_mapping:   dict[str, str]       = Field(default_factory=dict)
    max_parallel_runs: int                 = Field(1, ge=1, le=100)


# ============================================================================
# SECTION 9 — Observability & Logging (ADDITIONAL)
# ============================================================================

class TracingConfig(BaseModel):
    enabled:      bool          = Field(True)
    provider:     Literal["platform", "langsmith", "langfuse", "datadog", "custom"] = Field("platform")
    endpoint:     AnyHttpUrl | None = Field(None)
    sample_rate:  ZeroToOne     = Field(1.0, description="Fraction of traces to export (1.0 = 100%).")


class ObservabilityConfig(BaseModel):
    """
    Production systems NEED tracing. This is non-negotiable for debugging
    multi-step agentic runs, cost attribution, and SLA monitoring.
    """
    tracing:              TracingConfig = Field(default_factory=TracingConfig)
    log_inputs:           bool          = Field(True,  description="Persist user messages to the audit log.")
    log_outputs:          bool          = Field(True,  description="Persist agent responses to the audit log.")
    log_tool_calls:       bool          = Field(True)
    cost_tracking:        bool          = Field(True,  description="Record token usage and estimated cost per run.")
    evaluation_enabled:   bool          = Field(False, description="Auto-score outputs using an eval LLM.")
    feedback_enabled:     bool          = Field(True,  description="Allow users to thumbs-up/down responses.")


# ============================================================================
# SECTION 10 — Multi-Agent / Team Config (ADDITIONAL)
# ============================================================================

class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"   # Plans and delegates
    EXECUTOR     = "executor"       # Runs tasks
    CRITIC       = "critic"         # Reviews outputs
    RETRIEVER    = "retriever"      # Focused on data fetching
    STANDALONE   = "standalone"     # Classic single-agent


class MultiAgentConfig(BaseModel):
    """
    Declares the agent's position in a multi-agent system.
    Decoupled from tools/A2A so the orchestration topology is visible
    at the platform level without parsing tool configs.
    """
    role:              AgentRole         = Field(AgentRole.STANDALONE)
    team_id:           uuid.UUID | None  = Field(None, description="Parent team this agent belongs to.")
    collaborator_ids:  list[uuid.UUID]   = Field(default_factory=list, description="Peer agents it may coordinate with.")
    delegation_depth:  int               = Field(1, ge=1, le=5, description="Max orchestration hops downward.")
    consensus_mode:    Literal["first_wins", "majority_vote", "critic_review"] = Field("first_wins")


# ============================================================================
# SECTION 11 — Deployment & Runtime (ADDITIONAL)
# ============================================================================

class DeploymentConfig(BaseModel):
    """
    Operational concerns: where and how the agent runs.
    Kept separate from LLMConfig because an agent may switch providers
    without changing its deployment tier.
    """
    environment:      Literal["development", "staging", "production"] = Field("development")
    region:           str               = Field("us-east-1", description="Preferred cloud region for data residency.")
    replicas:         int               = Field(1, ge=1, le=100, description="Concurrent worker count.")
    auto_scale:       bool              = Field(False)
    idle_timeout_s:   int               = Field(300, ge=30, description="Seconds before an idle worker is suspended.")
    timezone:         str               = Field("UTC")
    whitelisted_ips:  list[str]         = Field(default_factory=list, description="CIDR ranges allowed to invoke this agent.")


# ============================================================================
# ROOT — CreateAgentRequest
# ============================================================================

class CreateAgentRequest(BaseModel):
    """
    Complete payload for creating an agent.

    All sections default to safe/empty configs so the frontend only needs to
    send the sections the user has touched. This also means partial saves
    (draft agents) work without extra logic.

    Sections map 1-to-1 with the 7 UI sections + 4 platform additions:
      1. identity          → Configure Identity
      2. llm               → Configure LLM
      3. prompt            → Configure Prompt
      4. memory            → Configure Memory
      5. tools             → Configure Tools
      6. guardrails        → Configure Guardrails
      7. output            → Configure Output
      8. workflow          → Workflow / Orchestration       [ADDED]
      9. observability     → Observability & Logging        [ADDED]
     10. multi_agent       → Multi-Agent / Team             [ADDED]
     11. deployment        → Deployment & Runtime           [ADDED]
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,          # Re-run validators on field updates
        populate_by_name=True,             # Accept both alias and field name
        json_schema_extra={                # Shown in /docs
            "title": "CreateAgentRequest",
            "description": "Full agent creation payload for the AI Agent Platform.",
        },
    )

    # --- Platform context (set by gateway, not the user) ---
    workspace_id:   uuid.UUID = Field(..., description="Owning workspace — injected by the auth middleware.")
    created_by:     uuid.UUID = Field(..., description="User UUID — injected by the auth middleware.")

    # --- The 7 user-configured sections ---
    identity:       IdentityConfig    = Field(...)
    llm:            LLMConfig         = Field(...)
    prompt:         PromptConfig      = Field(...)
    memory:         MemoryConfig      = Field(default_factory=MemoryConfig)
    tools:          ToolsConfig       = Field(default_factory=ToolsConfig)
    guardrails:     GuardrailsConfig  = Field(default_factory=GuardrailsConfig)
    output:         OutputConfig      = Field(default_factory=OutputConfig)

    # --- 4 additional platform sections ---
    workflow:       WorkflowConfig    = Field(default_factory=WorkflowConfig)
    observability:  ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    multi_agent:    MultiAgentConfig  = Field(default_factory=MultiAgentConfig)
    deployment:     DeploymentConfig  = Field(default_factory=DeploymentConfig)

    @model_validator(mode="after")
    def streaming_requires_stream_flag(self) -> "CreateAgentRequest":
        """Warn if output requests streaming but LLM stream flag is off."""
        if self.output.streaming.enabled and not self.llm.stream:
            # Auto-correct rather than error — better UX
            self.llm.stream = True
        return self

    @model_validator(mode="after")
    def workflow_cron_requires_expression(self) -> "CreateAgentRequest":
        wf = self.workflow
        if wf.enabled and wf.trigger == WorkflowTrigger.CRON and wf.cron is None:
            raise ValueError("workflow.cron must be set when trigger='cron'.")
        return self