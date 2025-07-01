import os
import shutil
import subprocess
import re
import json
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5179", "http://127.0.0.1:5179"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def extract_json(text: str):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None


def ask_openai(caption: str, duration: float):
    prompt = f"""
You are an Instagram growth expert with 5+ years of experience creating viral content. 
Analyze this Instagram Reel with professional depth:

VIDEO DETAILS:
- Duration: {duration} seconds
- Current Caption: "{caption}"

YOUR TASK:
1) current_caption_score (0-100): Evaluate based on:
   - Emotional resonance (0-30pts)
   - Curiosity gap (0-25pts)
   - Trend alignment (0-20pts)
   - Call-to-action (0-15pts)
   - Hashtag strategy (0-10pts)

2) caption_feedback: Provide 3-5 specific, actionable improvements

3) suggested_caption: Create 3 viral options following this structure:
   - Start with [EMOJI] + attention-grabber
   - Use "|" separators for scannability
   - Include 1 curiosity gap
   - Add subtle CTA
   Example: "🔥 Did you know THIS about...? | The results shocked me! | Try it & tag me 👇"

4) hashtags: Provide 8-10 relevant hashtags in this structure:
   - 3 broad (100k-1M posts)
   - 4 medium (10k-100k posts)
   - 3 niche (<10k posts)

5) viral_score (0-100): Calculate based on:
   - Content uniqueness (30%)
   - Engagement potential (25%)
   - Trend relevance (20%)
   - Production quality (15%)
   - Caption strength (10%)

6) viral_chance: High (>80)/Medium (50-80)/Low (<50) with confidence %

7) viral_reason: 3 data-backed reasons with Instagram algorithm insights

8) tips: 5 professional growth hacks including:
   - Hook timing suggestions
   - Text overlay improvements
   - Trending audio recommendations
   - Collaboration opportunities
   - Engagement boost strategies

9) best_post_time: 3 optimal posting windows with timezone
   Example: ["Weekdays 7-9PM EST", "Saturday 10-11AM EST", "Sunday 4-6PM EST"]

10) best_post_time_reason: Audience behavior analytics

Return ONLY this JSON structure:
{{
  "current_caption_score": int,
  "caption_feedback": str,
  "suggested_captions": [str, str, str],
  "hashtag_strategy": {{
    "broad": [str, str, str],
    "medium": [str, str, str, str],
    "niche": [str, str, str]
  }},
  "viral_score": int,
  "viral_chance": str,
  "viral_reasons": [str, str, str],
  "pro_tips": [str, str, str, str, str],
  "optimal_post_times": [str, str, str],
  "algorithm_insights": str
}}
"""
    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",  # Use latest GPT-4 model
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500
    )

    text = response.choices[0].message.content.strip()
    data = extract_json(text)

    if not data:
        return {
            "error": "Failed to analyze content",
            "details": "The AI response couldn't be processed. Please try again."
        }
    return data


@app.post("/upload-reel/")
async def upload_reel(file: UploadFile = File(...), caption: str = Form("")):
    try:
        # Save uploaded file
        file_location = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Get video duration
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_location,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        duration_sec = float(proc.stdout.strip()) if proc.returncode == 0 else 0.0

        # Get AI analysis
        ai_data = ask_openai(caption, duration_sec)

        if "error" in ai_data:
            return ai_data

        return {
            "filename": file.filename,
            "duration_seconds": duration_sec,
            **ai_data  # Spread all AI response data
        }

    except Exception as e:
        return {
            "error": "Processing failed",
            "details": str(e)
        }