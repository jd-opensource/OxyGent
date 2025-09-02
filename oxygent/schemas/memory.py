"""memory.py
Message and Memory Schemas
========================
"""

from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class Function(BaseModel):
    """OpenAI Chat Completions function call."""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """Represents a tool/function call in a message."""

    id: str
    type: str = "function"
    function: Function


# --------------------------------------------------------------------
# Chat message wrapper
# --------------------------------------------------------------------


class Message(BaseModel):
    """Represents a chat message in the conversation."""

    role: Literal["system", "user", "assistant", "tool"] = Field(...)
    content: Optional[Union[str, list, dict]] = Field(default=None)
    tool_calls: Optional[List[ToolCall]] = Field(default=None)
    name: Optional[str] = Field(default=None)
    tool_call_id: Optional[str] = Field(default=None)

    def __add__(self, other) -> List["Message"]:
        """Enable Message + list or Message + Message composition."""
        if isinstance(other, list):
            return [self] + other
        elif isinstance(other, Message):
            return [self, other]
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'"
            )

    def __radd__(self, other) -> List["Message"]:
        """支持 list + Message 的操作."""
        if isinstance(other, list):
            return other + [self]
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(other).__name__}' and '{type(self).__name__}'"
            )

    # ----------------------------------------------------------------
    # Converters
    # ----------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary(SDK-compatible) format."""
        message: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            message["content"] = self.content
        if self.tool_calls is not None:
            message["tool_calls"] = [
                tool_call.model_dump() for tool_call in self.tool_calls
            ]
        if self.name is not None:
            message["name"] = self.name
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        return message

    # ----------------------------------------------------------------
    # Factory constructors
    # ----------------------------------------------------------------
    """Shortcut of messages"""

    @classmethod
    def user_message(cls, content: Union[str, list]) -> "Message":
        """Create a user message."""
        return cls(role="user", content=content)

    @classmethod
    def system_message(cls, content: str) -> "Message":
        """Create a system message."""
        return cls(role="system", content=content)

    @classmethod
    def assistant_message(cls, content: Optional[str] = None) -> "Message":
        """Create an assistant message."""
        return cls(role="assistant", content=content)

    @classmethod
    def tool_message(cls, content: str, name, tool_call_id: str) -> "Message":
        """Create a tool message."""
        return cls(role="tool", content=content, name=name, tool_call_id=tool_call_id)

    # ----------------------------------------------------------------
    # Batch helpers
    # ----------------------------------------------------------------

    @classmethod
    def from_tool_calls(
        cls, tool_calls: List[Any], content: Union[str, List[str]] = "", **kwargs
    ):
        """Create ToolCallsMessage from raw tool calls.

        Args:
            tool_calls: Raw tool calls from LLM
            content: Optional message content
        """
        formatted_calls = [
            {"id": call.id, "function": call.function.model_dump(), "type": "function"}
            for call in tool_calls
        ]
        return cls(
            role="assistant", content=content, tool_calls=formatted_calls, **kwargs
        )

    # ----------------------------------------------------------------
    # Reverse conversion
    # ----------------------------------------------------------------

    @staticmethod
    def dict_list_to_messages(dict_list: list[dict[str, Any]]) -> List["Message"]:
        """Convert a list of dicts to a list of messages."""
        lookup = {
            "system": Message.system_message,
            "user": Message.user_message,
            "assistant": Message.assistant_message,
        }
        out: list[Message] = []
        for msg_dict in dict_list:
            role = msg_dict["role"]

            if role in lookup:
                out.append(lookup[role](msg_dict["content"]))
        return out


# --------------------------------------------------------------------
# Rolling memory buffer
# --------------------------------------------------------------------


class Memory(BaseModel):
    """Fixed-size sliding window of recent chat messages."""

    messages: List[Message] = Field(default_factory=list)
    max_messages: int = Field(default=50)

    def add_message(self, message: Message) -> None:
        """Add a message to memory."""
        self.messages.append(message)

    def add_messages(self, messages: List[Message]) -> None:
        """Add multiple messages to memory."""
        self.messages.extend(messages)

    def clear(self) -> None:
        """Drop all stored messages."""
        self.messages.clear()

    def get_recent_messages(self, n: int) -> List[Message]:
        """Get n most recent messages."""
        return self.messages[-n:]

    def to_dict_list(self, short_memory_size=None) -> List[dict]:
        """Convert messages to list of dicts (with trimming first)."""
        if short_memory_size is None:
            short_memory_size = self.max_messages // 2
        if len(self.messages) > short_memory_size * 2 + 2:
            messages = self.messages[0 - (short_memory_size * 2 + 1) :]
            if self.messages[0].role == "system":
                messages.insert(0, self.messages[0])
            return [msg.to_dict() for msg in messages]
        return [msg.to_dict() for msg in self.messages]

    # def _trim_memory(self) -> None:
    #     """Ensure memory does not exceed max_messages, keeping system first and deleting (user, agent) pairs."""
    #     while len(self.messages) > self.max_messages:
    #         if len(self.messages) <= 1:
    #             # Only system remains, nothing to delete
    #             break

    #         # Always keep system as the first message
    #         # Delete the first (user, agent) pair after system
    #         # Ensure at least two messages exist after system to delete
    #         if len(self.messages) >= 3:
    #             # Remove messages[1] and messages[2]
    #             del self.messages[1:3]
    #         else:
    #             # If only system + one message left but still exceeds max, delete the last
    #             self.messages.pop()
