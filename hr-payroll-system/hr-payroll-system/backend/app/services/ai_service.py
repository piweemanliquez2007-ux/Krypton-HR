import io
import json
import logging
from typing import Any, Dict, Optional
import requests
from pypdf import PdfReader

from app.config import settings
from app.errors import BusinessRuleError

logger = logging.getLogger(__name__)

RESUME_EXTRACTION_PROMPT = """
You are an expert HR assistant and resume parser.
Extract the following information from the provided resume text and return STRICT JSON with NO markdown formatting, no backticks, and no extra text:
{
  "first_name": "Candidate first name",
  "last_name": "Candidate last name",
  "email": "Candidate email",
  "phone": "Candidate phone number or null",
  "education": "Highest degree or university summary (max 200 chars)",
  "years_experience": 3.5,
  "skills": [
    {"name": "Skill 1", "confidence": 0.95},
    {"name": "Skill 2", "confidence": 0.85}
  ]
}

Guidelines:
1. Estimate "years_experience" as a float (e.g. 2.0, 3.5, 0.5) based on work dates. Default to 0.0 if not found.
2. For "skills", extract up to 10 key technical and soft skills, assigning a confidence score between 0.5 and 1.0.
3. Return ONLY valid JSON.
"""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts text content from PDF bytes using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n".join(text_parts).strip()
    except Exception as exc:
        logger.warning("Failed to extract text using pypdf: %s", exc)
        return ""


def parse_resume_with_gemini(resume_text: str, override_api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Calls Google Gemini API using override_api_key or the key configured in .env.
    Uses the modern x-goog-api-key header to support new AQ. format keys.
    """
    api_key = override_api_key or settings.gemini_api_key
    if not api_key or "YOUR_GEMINI_API_KEY" in api_key:
        raise BusinessRuleError("GEMINI_API_KEY is not configured. Please set your key in backend/.env or enter it in the upload form.")

    if not resume_text or len(resume_text.strip()) < 20:
        raise BusinessRuleError("Resume text is empty or too short to parse.")

    candidate_models = [
        settings.gemini_model or "gemini-flash-lite-latest",
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
    ]
    # Remove duplicates while preserving order
    models_to_try = list(dict.fromkeys(candidate_models))

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{RESUME_EXTRACTION_PROMPT}\n\nRESUME CONTENT:\n{resume_text[:12000]}"
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    last_error = None
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=25)
            if response.status_code == 200:
                res_data = response.json()
                raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                return json.loads(raw_text.strip())
            else:
                last_error = f"Model {model} returned {response.status_code}: {response.text}"
                logger.warning(last_error)
        except Exception as exc:
            last_error = f"Model {model} request failed: {exc}"
            logger.warning(last_error)

    raise BusinessRuleError(f"AI parsing failed on all models: {last_error}")


def call_gemini(
    contents: list[dict],
    override_api_key: Optional[str] = None,
    response_mime_type: str = "text/plain",
) -> str:
    """
    Generic Gemini text generation. Used by the chatbot.
    `contents` is a list of {"parts": [{"text": "..."}]} dicts.
    Returns the generated text string.
    """
    api_key = override_api_key or settings.gemini_api_key
    if not api_key or "YOUR_GEMINI_API_KEY" in api_key:
        raise BusinessRuleError("GEMINI_API_KEY is not configured.")

    candidate_models = [
        settings.gemini_model or "gemini-flash-lite-latest",
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
    ]
    models_to_try = list(dict.fromkeys(candidate_models))

    payload = {
        "contents": contents,
        "generationConfig": {
            "responseMimeType": response_mime_type,
            "temperature": 0.3,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    last_error = None
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                res_data = response.json()
                return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                last_error = f"Model {model} returned {response.status_code}: {response.text}"
                logger.warning(last_error)
        except Exception as exc:
            last_error = f"Model {model} request failed: {exc}"
            logger.warning(last_error)

    raise BusinessRuleError(f"AI request failed on all models: {last_error}")
