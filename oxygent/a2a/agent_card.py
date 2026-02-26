from __future__ import annotations

from fastapi import Request

from .schemas import AgentCapabilities, AgentCard, AgentInterface, AgentSkill


def build_agent_card(*, request: Request, a2a_prefix: str = "") -> AgentCard:
    base = str(request.base_url).rstrip("/")
    v1_url = f"{base}{a2a_prefix}/v1"
    return AgentCard(
        protocolVersion="0.3.0",
        name="OxyGent",
        description="OxyGent MAS A2A adapter (REST + SSE)",
        url=v1_url,
        preferredTransport="HTTP+JSON",
        additionalInterfaces=[AgentInterface(transport="HTTP+JSON", url=v1_url)],
        version="dev",
        capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            AgentSkill(
                id="chat",
                name="Chat",
                description="General chat with the OxyGent master agent.",
                inputModes=["text/plain"],
                outputModes=["text/plain"],
            )
        ],
    )
