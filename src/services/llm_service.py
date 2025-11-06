import json
import structlog
from typing import Optional, Dict, Any, List
from enum import Enum

import openai
import anthropic
import google.generativeai as genai

logger = structlog.get_logger(__name__)


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMService:
    """Multi-provider LLM service with automatic fallbacks."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None
    ):
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.google_api_key = google_api_key

        # Initialize clients
        self.openai_client = None
        self.anthropic_client = None
        self.google_client = None

        if openai_api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning("Failed to initialize OpenAI client", error=str(e))

        if anthropic_api_key:
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)
                logger.info("Anthropic client initialized")
            except Exception as e:
                logger.warning("Failed to initialize Anthropic client", error=str(e))

        if google_api_key:
            try:
                genai.configure(api_key=google_api_key)
                self.google_client = genai.GenerativeModel('gemini-pro')
                logger.info("Google Gemini client initialized")
            except Exception as e:
                logger.warning("Failed to initialize Google Gemini client", error=str(e))

    async def generate_with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4000,
        preferred_provider: Optional[LLMProvider] = None
    ) -> str:
        """
        Generate response with automatic fallback between providers.

        Fallback order (unless preferred_provider specified):
        1. OpenAI GPT-3.5-turbo (fast, reliable)
        2. Google Gemini Pro (good fallback)
        3. Anthropic Claude (high quality)
        """

        # If preferred provider specified, try it first
        if preferred_provider:
            try:
                return await self._generate_with_provider(
                    preferred_provider, system_prompt, user_prompt, temperature, max_tokens
                )
            except Exception as e:
                logger.warning(f"{preferred_provider} failed, trying fallbacks", error=str(e))

        # Try providers in fallback order
        providers_to_try = [LLMProvider.OPENAI, LLMProvider.GOOGLE, LLMProvider.ANTHROPIC]
        if preferred_provider:
            # Remove preferred from list since we already tried it
            providers_to_try = [p for p in providers_to_try if p != preferred_provider]

        for provider in providers_to_try:
            if self._is_provider_available(provider):
                try:
                    logger.info(f"Attempting generation with {provider}")
                    return await self._generate_with_provider(
                        provider, system_prompt, user_prompt, temperature, max_tokens
                    )
                except Exception as e:
                    logger.warning(f"{provider} failed, trying next provider", error=str(e))
                    continue

        raise ValueError("All LLM providers failed. Please check API keys and try again.")

    async def _generate_with_provider(
        self,
        provider: LLMProvider,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate response with specific provider."""

        if provider == LLMProvider.OPENAI:
            return await self._generate_openai(system_prompt, user_prompt, temperature, max_tokens)
        elif provider == LLMProvider.ANTHROPIC:
            return await self._generate_anthropic(system_prompt, user_prompt, temperature, max_tokens)
        elif provider == LLMProvider.GOOGLE:
            return await self._generate_google(system_prompt, user_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _generate_openai(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
        """Generate using OpenAI GPT."""
        if not self.openai_client:
            raise ValueError("OpenAI client not available")

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            result = response.choices[0].message.content
            logger.info("OpenAI generation completed", response_length=len(result))
            return result

        except openai.AuthenticationError as e:
            raise ValueError(f"OpenAI authentication failed: {str(e)}")
        except openai.RateLimitError as e:
            raise ValueError(f"OpenAI rate limit exceeded: {str(e)}")
        except Exception as e:
            raise ValueError(f"OpenAI generation failed: {str(e)}")

    async def _generate_anthropic(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
        """Generate using Anthropic Claude."""
        if not self.anthropic_client:
            raise ValueError("Anthropic client not available")

        try:
            # Combine system and user prompts for Claude
            full_prompt = f"System: {system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:"

            response = self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": full_prompt}
                ]
            )
            result = response.content[0].text
            logger.info("Anthropic generation completed", response_length=len(result))
            return result

        except Exception as e:
            raise ValueError(f"Anthropic generation failed: {str(e)}")

    async def _generate_google(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
        """Generate using Google Gemini."""
        if not self.google_client:
            raise ValueError("Google client not available")

        try:
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens
            )

            # Combine prompts for Gemini
            full_prompt = f"{system_prompt}\n\nUser: {user_prompt}"

            response = self.google_client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            result = response.text
            logger.info("Google generation completed", response_length=len(result))
            return result

        except Exception as e:
            raise ValueError(f"Google generation failed: {str(e)}")

    def _is_provider_available(self, provider: LLMProvider) -> bool:
        """Check if provider is available (has client initialized)."""
        if provider == LLMProvider.OPENAI:
            return self.openai_client is not None
        elif provider == LLMProvider.ANTHROPIC:
            return self.anthropic_client is not None
        elif provider == LLMProvider.GOOGLE:
            return self.google_client is not None
        return False

    def get_available_providers(self) -> List[LLMProvider]:
        """Get list of available LLM providers."""
        providers = []
        if self.openai_client:
            providers.append(LLMProvider.OPENAI)
        if self.anthropic_client:
            providers.append(LLMProvider.ANTHROPIC)
        if self.google_client:
            providers.append(LLMProvider.GOOGLE)
        return providers

    async def parse_json_response(self, response: str) -> Dict[str, Any]:
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            # Find first complete JSON object or array
            for start_char, end_char in [('[', ']'), ('{', '}')]:
                start = response.find(start_char)
                if start == -1:
                    continue

                count = 0
                for i, char in enumerate(response[start:], start):
                    if char == start_char:
                        count += 1
                    elif char == end_char:
                        count -= 1
                        if count == 0:
                            try:
                                return json.loads(response[start:i+1])
                            except:
                                continue

            return [] if '[' in response else {}