"""oxy_factory.py Factory for creating OxyGent operators.xs."""

from .oxy import (
    ChatAgent,
    FunctionTool,
    HttpLLM,
    HttpTool,
    MCPTool,
    OpenAILLM,
    ReActAgent,
    SSEMCPClient,
    StdioMCPClient,
    Workflow,
    WorkflowAgent,
)


class OxyFactory:
    _creators = {
        "ChatAgent": ChatAgent,
        "ReActAgent": ReActAgent,
        "WorkflowAgent": WorkflowAgent,
        "HttpTool": HttpTool,
        "HttpLLM": HttpLLM,
        "OpenAILLM": OpenAILLM,
        "MCPTool": MCPTool,
        "StdioMCPClient": StdioMCPClient,
        "SSEMCPClient": SSEMCPClient,
        "FunctionTool": FunctionTool,
        "Workflow": Workflow,
    }

    @staticmethod
    def create_oxy(operator_class_name, **kwargs):
        try:
            return OxyFactory._creators[operator_class_name](**kwargs)
        except KeyError:
            raise ValueError(f"Unknown animal type: {operator_class_name}")
