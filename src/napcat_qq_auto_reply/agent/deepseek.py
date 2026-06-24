import logging
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import ConfigDict


DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekChatOpenAI(ChatOpenAI):
    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        messages = self._convert_input(input_).to_messages()
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        for source, target in zip(messages, payload.get("messages", []), strict=False):
            if isinstance(source, AIMessage):
                reasoning = source.additional_kwargs.get("reasoning_content")
                if reasoning:
                    target.setdefault("reasoning_content", reasoning)
        return payload

    def _create_chat_result(self, response: Any, generation_info=None) -> ChatResult:
        response_dict = response if isinstance(response, dict) else response.model_dump()
        reasoning = [
            (choice.get("message") or {}).get("reasoning_content")
            for choice in response_dict.get("choices", [])
        ]
        result = super()._create_chat_result(response, generation_info)
        for generation, value in zip(result.generations, reasoning, strict=False):
            if value:
                generation.message.additional_kwargs["reasoning_content"] = value
        return result


class FallbackLLM(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    primary: object = None
    fallback: object = None

    @property
    def _llm_type(self) -> str:
        return "deepseek-fallback"

    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs,
    ) -> ChatResult:
        try:
            return self.primary._generate(messages, stop, run_manager, **kwargs)
        except Exception:
            logging.exception("Primary DeepSeek model failed; using fallback")
            return self.fallback._generate(messages, stop, run_manager, **kwargs)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        try:
            return await self.primary._agenerate(messages, stop, run_manager, **kwargs)
        except Exception:
            logging.exception("Primary DeepSeek model failed; using fallback")
            return await self.fallback._agenerate(messages, stop, run_manager, **kwargs)

    def bind_tools(self, tools, **kwargs):
        primary = self.primary.bind_tools(tools, **kwargs)
        fallback = self.fallback.bind_tools(tools, **kwargs)

        async def ainvoke(value, config=None, **call_kwargs):
            try:
                return await primary.ainvoke(value, config, **call_kwargs)
            except Exception:
                logging.exception("Primary DeepSeek tool call failed; using fallback")
                return await fallback.ainvoke(value, config, **call_kwargs)

        def invoke(value, config=None, **call_kwargs):
            try:
                return primary.invoke(value, config, **call_kwargs)
            except Exception:
                logging.exception("Primary DeepSeek tool call failed; using fallback")
                return fallback.invoke(value, config, **call_kwargs)

        return RunnableLambda(invoke, afunc=ainvoke)


def build_deepseek_llm(config) -> FallbackLLM:
    if config.deepseek_thinking not in {"enabled", "disabled"}:
        raise ValueError("DEEPSEEK_MENTION_THINKING must be enabled or disabled")

    def create(model_name: str):
        kwargs = {
            "model": model_name,
            "api_key": config.deepseek_api_key,
            "base_url": DEEPSEEK_BASE_URL,
            "max_retries": 3,
            "extra_body": {"thinking": {"type": config.deepseek_thinking}},
        }
        if config.deepseek_thinking == "enabled":
            kwargs["reasoning_effort"] = "max"
        return DeepSeekChatOpenAI(**kwargs)

    return FallbackLLM(
        primary=create(config.deepseek_model),
        fallback=create(config.deepseek_fallback_model),
    )
