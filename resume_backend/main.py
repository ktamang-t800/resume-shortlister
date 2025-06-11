from fastapi import FastAPI, Request
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import os

# Load your .env file (should contain your OpenAI API key)
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# Request models
class ShortlistRequest(BaseModel):
    job_description: str
    resume_text: str

class VerdictRequest(BaseModel):
    job_description: str
    resume_text: str

# =========== Endpoint: Score (0–10) + Summary (Optional) ===========
@app.post("/score")
async def score_resume(data: ShortlistRequest, request: Request):
    if not OPENAI_API_KEY:
        return {"score": 0, "summary": "OpenAI key not set"}
    try:
        prompt = f"""
Given the job description and resume, rate the resume's relevance on a 0-10 scale and provide a brief summary of strengths/weaknesses.
Respond as JSON: {{"score": <score>, "summary": "<summary>"}}

Job Description:
{data.job_description}

Resume:
{data.resume_text}
"""
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",  # Use gpt-4.1-nano if you have access
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=350
        )
        import json as pyjson
        text = response.choices[0].message.content
        result = pyjson.loads(text)
        return result
    except Exception as e:
        return {"score": 0, "summary": f"Error: {str(e)}"}

# =========== Endpoint: Detailed Profile Card Verdict ===========
@app.post("/gpt_verdict")
async def gpt_verdict(data: VerdictRequest, request: Request):
    if not OPENAI_API_KEY:
        return {"result": "OpenAI key not set"}
    try:
        prompt = f"""
You are an expert HR Analyst.

Compare the following Job Description and Resume.

- Give a final assessment (Strong Match, Moderate Match, Not a Match, etc.) for shortlisting, and explain why.
- Create a table: "Key Matching Areas" with columns [JD Requirement, Candidate Experience] (show at least 5 points).
- Create a table: "Minor Gaps (if any)" with columns [Gap, Mitigation] (show up to 3 points, or say "None").
- Keep it brief, professional, and formatted for direct use (using markdown for tables).

Job Description:
{data.job_description}

Candidate Resume:
{data.resume_text}
"""
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",  # Use "gpt-4.1-nano" for best formatting/results
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800
        )
        verdict_text = response.choices[0].message.content
        return {"result": verdict_text}
    except Exception as e:
        return {"result": f"Error: {str(e)}"}

# =========== Health Check ===========
@app.get("/")
async def root():
    return {"message": "Resume Shortlisting API is running."}
