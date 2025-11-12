from langchain_core.callbacks.base import BaseCallbackHandler


class CustomCallbackHandler(BaseCallbackHandler):
    """Custom callback handler to handle events during the execution of a language model."""

    def on_llm_start(self, serialized, prompts, **kwargs) -> None:
        print("LLM started with prompts:", prompts)

    def on_llm_end(self, response, **kwargs) -> None:
        print("LLM finished with response:", response)

    def on_chain_start(self, serialized, inputs, **kwargs) -> None:
        print("Chain started with inputs:", inputs)

    def on_chain_end(self, outputs, **kwargs) -> None:
        print("Chain finished with outputs:", outputs)

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        print("Tool started with input:", input_str)

    def on_tool_end(self, output_str, **kwargs) -> None:
        print("Tool finished with output:", output_str)

    def on_text(self, text: str, **kwargs) -> None:
        print("Text event:", text)

    def on_agent_action(self, action: dict, **kwargs) -> None:
        print("Agent action:", action)

    def on_agent_finish(self, finish: dict, **kwargs) -> None:
        print("Agent finished with result:", finish)
