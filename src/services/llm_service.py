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
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        openai_model_name: str = "gpt-4o-mini",
        anthropic_model_name: str = "claude-3-haiku-20240307",
        google_model_name: str = "gemini-1.5-flash"
    ):
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.google_api_key = google_api_key
        self.openai_model_name = openai_model_name
        self.anthropic_model_name = anthropic_model_name
        self.google_model_name = google_model_name

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
                self.google_client = genai.GenerativeModel(self.google_model_name)
                logger.info("Google Gemini client initialized")
            except Exception as e:
                logger.warning("Failed to initialize Google Gemini client", error=str(e))

    async def generate_with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 10000,
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
                model=self.openai_model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            result = response.choices[0].message.content
            logger.info("OpenAI generation completed", model=self.openai_model_name, response_length=len(result))
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
                model=self.anthropic_model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": full_prompt}
                ]
            )
            result = response.content[0].text
            logger.info("Anthropic generation completed", model=self.anthropic_model_name, response_length=len(result))
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
            for start_char, end_char in [('{', '}'), ('[', ']')]:
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

    def upload_file(self, file_path: str, mime_type: Optional[str] = None) -> Any:
        """
        Upload a file to Google Gemini API.

        Args:
            file_path: Path to the file to upload
            mime_type: Optional MIME type of the file

        Returns:
            Uploaded file object
        """
        if not self.google_client:
            raise ValueError("Google Gemini client not available")

        try:
            logger.info("Uploading file to Gemini", file_path=file_path)
            if mime_type:
                file = genai.upload_file(file_path, mime_type=mime_type)
            else:
                file = genai.upload_file(file_path)
            
            logger.info("File uploaded to Gemini", file_name=file.name, uri=file.uri)
            return file

        except Exception as e:
            raise ValueError(f"Failed to upload file to Gemini: {str(e)}")

    async def wait_for_files_active(self, files: List[Any], timeout: int = 300) -> None:
        """
        Wait for uploaded files to be processed and active.

        Args:
            files: List of uploaded file objects
            timeout: Maximum wait time in seconds
        """
        import time
        import asyncio

        logger.info("Waiting for Gemini files to be processed...")
        
        start_time = time.time()
        for file in files:
            while file.state.name == "PROCESSING":
                if time.time() - start_time > timeout:
                    raise ValueError(f"Timeout waiting for file processing: {file.name}")
                
                await asyncio.sleep(2)
                file = genai.get_file(file.name)

            if file.state.name != "ACTIVE":
                raise ValueError(f"File processing failed: {file.name}, state: {file.state.name}")

        logger.info("All Gemini files processed and active")

    async def generate_video_content(
        self,
        video_url: str = None,
        video_file: Any = None,
        prompt: str = "",
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 10000
    ) -> str:
        """
        Generate content analysis for video using Google Gemini's video understanding API.

        Args:
            video_url: YouTube URL (deprecated for direct analysis, used contextually)
            video_file: Uploaded Gemini file object (preferred)
            prompt: Analysis prompt for the video
            model_name: Gemini model to use
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated analysis response
        """
        if not self.google_client:
            raise ValueError("Google Gemini client not available. Check API key.")

        # Use configured model name if not specified
        if model_name is None:
            model_name = self.google_model_name

        try:
            logger.info("Starting Gemini video analysis", model=model_name)

            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens
            )

            # Create model instance
            model = genai.GenerativeModel(model_name)

            content_parts = []
            
            # If we have a file object, use it directly (this is the reliable way)
            if video_file:
                logger.info("Using uploaded video file for analysis", file_uri=video_file.uri)
                content_parts.append(video_file)
                content_parts.append(prompt)
            
            # Fallback (legacy): If only URL is provided, try to use it in prompt (unreliable)
            elif video_url:
                logger.warning("Using legacy URL-based analysis (prone to hallucinations)", video_url=video_url)
                full_prompt = f"Analyze the YouTube video at: {video_url}\n\n{prompt}"
                content_parts.append(full_prompt)
            
            else:
                raise ValueError("Either video_file or video_url must be provided")

            response = model.generate_content(
                content_parts,
                generation_config=generation_config
            )

            result = response.text
            logger.info(
                "Gemini video analysis completed",
                response_length=len(result)
            )
            return result

        except Exception as e:
            error_msg = f"Gemini video analysis failed: {str(e)}"
            logger.error(
                "Video analysis error",
                error=error_msg,
                exc_info=True
            )
            # Check for recitations error (copyright)
            if "RECITATION" in str(e):
                 raise ValueError(f"Content blocked due to copyright/recitation check: {str(e)}")
                 
            raise ValueError(error_msg)

    def supports_video_analysis(self) -> bool:
        """
        Check if the service supports video analysis.

        Returns:
            True if Google Gemini with video capabilities is available
        """
        return self.google_client is not None and self.google_api_key is not None

    def get_video_model_name(self) -> str:
        """
        Get the configured model name for video analysis.

        Returns:
            Model name string for video processing
        """
        return self.google_model_name