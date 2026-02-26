from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class A2ABaseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class AgentCapabilities(A2ABaseModel):
    streaming: bool = False
    pushNotifications: bool = False


class AgentInterface(A2ABaseModel):
    transport: str
    url: str


class AgentSkill(A2ABaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    examples: Optional[list[str]] = None
    inputModes: Optional[list[str]] = None
    outputModes: Optional[list[str]] = None


class AgentCard(A2ABaseModel):
    protocolVersion: str = "0.3.0"
    name: str
    description: str
    url: str
    preferredTransport: Optional[str] = None
    additionalInterfaces: Optional[list[AgentInterface]] = None
    iconUrl: Optional[str] = None
    provider: Optional[dict[str, Any]] = None
    version: str
    documentationUrl: Optional[str] = None
    capabilities: AgentCapabilities
    securitySchemes: Optional[dict[str, Any]] = None
    security: Optional[list[dict[str, list[str]]]] = None
    defaultInputModes: list[str] = Field(default_factory=list)
    defaultOutputModes: list[str] = Field(default_factory=list)
    skills: list[AgentSkill] = Field(default_factory=list)


class TaskState(str, Enum):
    submitted = "submitted"
    working = "working"
    input_required = "input-required"
    completed = "completed"
    canceled = "canceled"
    failed = "failed"
    rejected = "rejected"
    auth_required = "auth-required"
    unknown = "unknown"


class TextPart(A2ABaseModel):
    kind: Literal["text"] = "text"
    text: str
    metadata: Optional[dict[str, Any]] = None


class Message(A2ABaseModel):
    kind: Literal["message"] = "message"
    role: Literal["user", "agent"]
    parts: list[dict[str, Any]]
    messageId: str
    taskId: Optional[str] = None
    contextId: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    extensions: Optional[list[str]] = None
    referenceTaskIds: Optional[list[str]] = None


class TaskStatus(A2ABaseModel):
    state: TaskState
    message: Optional[Message] = None


class Artifact(A2ABaseModel):
    artifactId: str
    name: Optional[str] = None
    description: Optional[str] = None
    parts: list[dict[str, Any]]
    metadata: Optional[dict[str, Any]] = None
    extensions: Optional[list[str]] = None


class Task(A2ABaseModel):
    kind: Literal["task"] = "task"
    id: str
    contextId: str
    status: TaskStatus
    history: Optional[list[Message]] = None
    artifacts: Optional[list[Artifact]] = None
    metadata: Optional[dict[str, Any]] = None


class TaskStatusUpdateEvent(A2ABaseModel):
    kind: Literal["status-update"] = "status-update"
    taskId: str
    contextId: str
    status: TaskStatus
    final: bool
    metadata: Optional[dict[str, Any]] = None


class TaskArtifactUpdateEvent(A2ABaseModel):
    kind: Literal["artifact-update"] = "artifact-update"
    taskId: str
    contextId: str
    artifact: Artifact
    append: Optional[bool] = None
    lastChunk: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None


class MessageSendConfiguration(A2ABaseModel):
    acceptedOutputModes: Optional[list[str]] = None
    historyLength: Optional[int] = None
    pushNotificationConfig: Optional[dict[str, Any]] = None
    blocking: Optional[bool] = None


class MessageSendRequest(A2ABaseModel):
    message: Message
    configuration: Optional[MessageSendConfiguration] = None
    metadata: Optional[dict[str, Any]] = None


class MessageSendResponse(A2ABaseModel):
    message: Optional[Message] = None
    task: Optional[Task] = None
