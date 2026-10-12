import json
import logging
import time
from typing import Optional

import openai

from app.core.config import settings
from app.schemas.guidance import ExtractionResult

logger = logging.getLogger(__name__)

DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MAX_TOKENS = 8000
TEMPERATURE = 0.0


class LLMGateway:
    def __init__(self):
        self.client = None
        if settings.deepseek_api_key:
            self.client = openai.OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=DEEPSEEK_BASE_URL,
            )

    async def extract_guidance(
        self,
        prompt: str,
        document_text: str,
        model: str = DEEPSEEK_MODEL,
    ) -> ExtractionResult:
        document_text = _sanitize_text(document_text)
        full_prompt = prompt.replace("{document_chunk}", document_text)
        raw = await self._call_deepseek_with_retry(full_prompt, model)
        return self._parse_extraction_response(raw)

    async def extract_guidance_from_chunks(
        self,
        prompt: str,
        chunks: list[str],
        model: str = DEEPSEEK_MODEL,
    ) -> ExtractionResult:
        combined = "\n\n--- NEXT DOCUMENT SECTION ---\n\n".join(chunks)
        return await self.extract_guidance(prompt, combined, model)

    async def _call_deepseek_with_retry(
        self,
        prompt: str,
        model: str,
        max_retries: int = 5,
    ) -> str:
        if not self.client:
            return "{}"

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    extra_body={"thinking": {"type": "disabled"}},
                )
                content = response.choices[0].message.content
                finish = response.choices[0].finish_reason
                if finish == "length":
                    logger.warning("LLM response truncated (finish_reason=length)")
                return content or "{}"

            except openai.RateLimitError:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise

            except openai.APIStatusError as e:
                logger.error(f"DeepSeek API error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return "{}"

            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    return "{}"

        return "{}"

    def _parse_extraction_response(self, raw: str) -> ExtractionResult:
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw.removeprefix("```json").removesuffix("```").strip()
        elif raw.startswith("```"):
            raw = raw.removeprefix("```").removesuffix("```").strip()

        # Try standard JSON first
        try:
            data = json.loads(raw)
            return ExtractionResult(**data)
        except json.JSONDecodeError:
            pass

        # Try repairing common LLM JSON issues
        repaired = self._repair_json(raw)
        try:
            data = json.loads(repaired)
            return ExtractionResult(**data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return ExtractionResult(extraction_notes=f"Parse error: {str(e)}")

    @staticmethod
    def _repair_json(raw: str) -> str:
        import re
        # Remove trailing commas before ] or }
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        # Replace single quotes with double quotes (for keys and simple values)
        # Try to extract just the JSON object
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            raw = match.group(0)
        return raw


_llm_gateway: Optional[LLMGateway] = None


def _sanitize_text(text: str) -> str:
    import re
    # Replace problematic Unicode with ASCII equivalents
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "--")
    text = text.replace(" ", " ")
    # Strip remaining non-ASCII that can break API calls
    text = text.encode("ascii", errors="replace").decode("ascii")
    text = text.replace("?", "'")  # common replacement char
    # Collapse whitespace
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_llm_gateway() -> LLMGateway:
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway
