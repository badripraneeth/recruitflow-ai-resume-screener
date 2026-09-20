"""
LLM Service integration layer.
Interacts with the LLM API using environment variables (LLM_API_KEY or GEMINI_API_KEY).
Handles API errors, timeouts, clean JSON stripping, and fallback mock capabilities for tests.
"""

import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


class LLMConfigurationError(Exception):
    """Raised when LLM API keys or essential provider configurations are missing."""
    pass


class LLMAPIError(Exception):
    """Raised when the LLM service API call encounters an error or returns an error response."""
    pass


class LLMTimeoutError(LLMAPIError):
    """Raised when the LLM service request times out."""
    pass


class LLMJSONDecodeError(ValueError):
    """Raised when the LLM output cannot be parsed as valid JSON."""
    pass


def get_llm_api_key():
    """
    Safely retrieves the LLM API key from environment variables.
    Never exposed to frontend or template contexts.
    Checks: LLM_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY.
    """
    key = os.getenv('LLM_API_KEY') or os.getenv('GEMINI_API_KEY') or os.getenv('OPENAI_API_KEY')
    return key.strip() if key else None


def clean_json_response(raw_text):
    """
    Strips markdown code block backticks (e.g. ```json ... ```) from LLM output.
    Returns clean JSON string ready for json.loads.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    text = raw_text.strip()

    # Remove markdown code blocks if present
    if text.startswith('```'):
        # Remove opening ``` or ```json
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
        # Remove closing ```
        text = re.sub(r'\s*```$', '', text)

    return text.strip()


class LLMService:
    """
    Unified LLM service interfacing with Gemini or OpenAI-compatible providers.
    Enforces structured JSON output and strict error handling.
    """
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or get_llm_api_key()
        self.model_name = model_name or os.getenv('LLM_MODEL', 'gemini-3.6-flash')
        self.mock_mode = os.getenv('MOCK_LLM', 'False').lower() in ('true', '1', 'yes')

    def generate_json(self, system_prompt, user_prompt, timeout=60):
        """
        Executes an inference request against the LLM and returns parsed JSON.
        Handles timeouts, API errors, and JSON decode failures.
        """
        if self.mock_mode or not self.api_key:
            # If no API key configured and in testing/local mode, provide a structured mock
            if not self.api_key and not self.mock_mode:
                raise LLMConfigurationError(
                    "LLM_API_KEY is not configured in .env. Please configure LLM_API_KEY or GEMINI_API_KEY."
                )
            return self._generate_mock_response(user_prompt)

        # Attempt Gemini API first if google-generativeai is available
        try:
            return self._call_gemini(system_prompt, user_prompt, timeout=timeout)
        except Exception as gemini_err:
            # If Gemini fails or key is OpenAI, attempt OpenAI
            if 'openai' in str(gemini_err).lower() or os.getenv('OPENAI_API_KEY'):
                try:
                    return self._call_openai(system_prompt, user_prompt, timeout=timeout)
                except Exception as openai_err:
                    raise LLMAPIError(f"LLM API request failed: {str(openai_err)}") from openai_err
            raise LLMAPIError(f"Gemini API request failed: {str(gemini_err)}") from gemini_err

    def _call_gemini(self, system_prompt, user_prompt, timeout=60):
        import google.generativeai as genai
        from google.api_core.exceptions import GoogleAPICallError, DeadlineExceeded, NotFound

        genai.configure(api_key=self.api_key)
        
        generation_config = {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        }

        candidate_models = [self.model_name]
        for fallback in ('gemini-3.6-flash', 'gemini-flash-latest', 'gemini-2.5-flash'):
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_err = None
        for m_name in candidate_models:
            try:
                model = genai.GenerativeModel(
                    model_name=m_name,
                    system_instruction=system_prompt,
                    generation_config=generation_config
                )

                response = model.generate_content(
                    user_prompt,
                    request_options={"timeout": timeout}
                )

                raw_text = response.text if hasattr(response, 'text') else str(response)
                cleaned = clean_json_response(raw_text)

                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError as decode_err:
                    raise LLMJSONDecodeError(f"LLM did not return valid JSON: {str(decode_err)}\nRaw text: {raw_text[:300]}")

            except NotFound as not_found_err:
                last_err = not_found_err
                continue
            except DeadlineExceeded as timeout_err:
                last_err = timeout_err
                continue
            except GoogleAPICallError as api_err:
                last_err = api_err
                continue

        raise LLMAPIError(f"Gemini API call failed across models: {str(last_err)}")

    def _call_openai(self, system_prompt, user_prompt, timeout=60):
        from openai import OpenAI, APITimeoutError, APIError

        client = OpenAI(api_key=self.api_key)
        try:
            response = client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                timeout=timeout
            )
            raw_text = response.choices[0].message.content
            cleaned = clean_json_response(raw_text)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as decode_err:
                raise LLMJSONDecodeError(f"LLM did not return valid JSON: {str(decode_err)}")
        except APITimeoutError as to_err:
            raise LLMTimeoutError(f"OpenAI API timed out after {timeout} seconds") from to_err
        except APIError as api_err:
            raise LLMAPIError(f"OpenAI API error: {str(api_err)}") from api_err

    def _generate_mock_response(self, user_prompt):
        """
        Generates a valid structured mock analysis when running in mock mode or automated tests.
        """
        return {
            "candidate_name": "Sample Candidate",
            "candidate_email": "candidate@example.com",
            "skills": ["Python", "Django", "PostgreSQL", "Git"],
            "experience_years": 3.5,
            "education": [
                {
                    "degree": "B.Tech",
                    "field": "Computer Science"
                }
            ],
            "projects": [
                {
                    "name": "Cloud Screening Service",
                    "description": "Built resilient backend architecture using Django and PostgreSQL."
                }
            ],
            "matched_required_skills": ["Python", "Django"],
            "missing_required_skills": [],
            "matched_preferred_skills": ["PostgreSQL"],
            "missing_preferred_skills": ["AWS", "Docker"],
            "ai_summary": "Demonstrates solid hands-on experience in core Python and Django web development."
        }
