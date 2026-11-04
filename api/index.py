import os
from dotenv import load_dotenv  # type: ignore
from fastapi import Depends, FastAPI, HTTPException  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi_clerk_auth import (  # type: ignore
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)
from google import genai  # type: ignore
from google.genai import types  # type: ignore
from pydantic import BaseModel  # type: ignore

# Load environment variables
load_dotenv()
load_dotenv(".env.local")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jwks_url = os.getenv("CLERK_JWKS_URL")
if not jwks_url:
    raise ValueError(
        "CLERK_JWKS_URL is missing. Please set it in your .env or .env.local file."
    )

clerk_config = ClerkConfig(jwks_url=jwks_url)
clerk_guard = ClerkHTTPBearer(clerk_config)

# Can be overridden with a GEMINI_MODEL env var in Vercel, no code change needed
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


class Visit(BaseModel):
    patient_name: str
    date_of_visit: str
    notes: str


system_prompt = """
You are provided with notes written by a doctor from a patient's visit.
Your job is to summarize the visit for the doctor and provide an email.
Reply with exactly three sections with the headings:
### Summary of visit for the doctor's records
### Next steps for the doctor
### Draft of email to patient in patient-friendly language
"""


def user_prompt_for(visit: Visit) -> str:
    return f"""Create the summary, next steps and draft email for:
Patient Name: {visit.patient_name}
Date of Visit: {visit.date_of_visit}
Notes:
{visit.notes}"""


@app.post("/api")
def consultation_summary(
    visit: Visit,
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is missing on the server.",
        )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt_for(visit),
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        return {"text": response.text or "No response generated."}
    except Exception as e:
        print(f"Gemini error: {e!r}")
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")