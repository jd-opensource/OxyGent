import copy

from pydantic import AnyUrl, Field, field_validator

from ...schemas import OxyRequest, OxyResponse
from .base_agent import BaseAgent


class RemoteAgent(BaseAgent):
    """Base class for agents that communicate with remote systems.

    This agent provides the foundation for connecting to and interacting with
    remote agent systems over HTTP/HTTPS.

    Attributes:
        server_url (AnyUrl): The URL of the remote agent server.
        org (dict): Organization structure from the remote system.
    """

    server_url: AnyUrl = Field()
    org: dict = Field(default_factory=dict)

    @field_validator("server_url")
    def check_protocol(cls, v):
        if v.scheme not in ("http", "https"):
            raise ValueError("server_url must start with http:// or https://")
        return v

    def get_org(self):
        # Add remote prefix to the copy
        def update_children(children):
            for node in children:
                node["is_remote"] = True
                if "children" in node and isinstance(node["children"], list):
                    update_children(node["children"])
            return children

        # Create deep copy and mark as remote
        children_copy = copy.deepcopy(self.org["children"])
        return update_children(children_copy)

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        raise NotImplementedError("This method is not yet implemented")
