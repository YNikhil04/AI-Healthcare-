import os
from pathlib import Path
from fastapi import FastAPI, Depends # type: ignore[import-not-found]
from fastapi.responses import StreamingResponse, FileResponse # type: ignore[import-not-found]
from fastapi.staticfiles import StaticFiles # type: ignore[import-not-found]
from fastapi.middleware.cors import CORSMiddleware # type: ignore[import-not-found]
from pydantic import BaseModel # type: ignore[import-not-found]
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials # type: ignore[import-not-found]
from google import genai # type: ignore[import-not-found]
from google.genai import types  # type: ignore[import-not-found]

app = FastAPI()

# Add CORS middleware (allows frontend to call backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clerk authentication setup
clerk_config = ClerkConfig(jwks_url=os.getenv("CLERK_JWKS_URL"))
clerk_guard = ClerkHTTPBearer(clerk_config)

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

@app.post("/api/consultation")
def consultation_summary(
    visit: Visit,
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    user_id = creds.decoded["sub"]
    user_prompt = user_prompt_for(visit)

    def event_stream():
        # Client is created inside the generator so it stays alive
        # for the whole stream (otherwise it gets closed too early).
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        try:
            stream = client.models.generate_content_stream(
                model="gemini-3.5-flash-lite",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                ),
            )
            for chunk in stream:
                text = chunk.text
                if text:
                    lines = text.split("\n")
                    for line in lines[:-1]:
                        yield f"data: {line}\n\n"
                        yield "data:  \n"
                    yield f"data: {lines[-1]}\n\n"
        except Exception as e:
            print(f"Gemini error: {e!r}")
            yield f"data: \n\n"
            yield f"data: **Error while generating:** {e}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/health")
def health_check():
    """Health check endpoint (used for local Docker; Lambda does not invoke it)"""
    return {"status": "healthy"}

# Serve static files (our Next.js export) - MUST BE LAST!
static_path = Path("static")
if static_path.exists():
    @app.get("/")
    async def serve_root():
        return FileResponse(static_path / "index.html")

    app.mount("/", StaticFiles(directory="static", html=True), name="static")