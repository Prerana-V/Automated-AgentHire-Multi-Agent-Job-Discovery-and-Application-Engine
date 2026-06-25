"""
multiagent/career_intelligence.py — The Groq-powered reasoning core, handles: job matching, resume tailoring, cover letter writing.
"""

from __future__ import annotations
import json
import re
from typing import Optional
from groq import Groq
from rich.console import Console
from config import EnvConfig, JobListing, MatchAnalysis, TailoredApplication

console = Console()
_client: Optional[Groq] = None


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=EnvConfig.GROQ_API_KEY)
    return _client


# ── Resume loader ──────────────────────────────────────────────────────
def load_resume(resume_path: str) -> str:
    """Load plain-text resume from file."""
    try:
        with open(resume_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return _sample_resume()



def _sample_resume() -> str:
    return f"""
{EnvConfig.CANDIDATE_NAME}
{EnvConfig.CANDIDATE_EMAIL} | {EnvConfig.CANDIDATE_PHONE}
{EnvConfig.CANDIDATE_LINKEDIN} | {EnvConfig.CANDIDATE_GITHUB}

SUMMARY
AI/ML Engineer and Data Scientist with hands-on experience in machine learning, NLP, computer vision, LLM fine-tuning, and Generative AI systems. Experienced in building AI-powered applications, transformer-based workflows, model evaluation systems, and predictive analytics using Python, TensorFlow, Hugging Face, and Scikit-learn. Interested in AI/ML Engineering, Generative AI, Machine Learning, and Data Science roles focused on scalable, production-ready intelligent systems.

SKILLS
Languages:
Python, SQL

Machine Learning & AI:
Machine Learning, Deep Learning, NLP, Generative AI, LLM Fine-Tuning, Prompt Engineering, Transformers, Computer Vision, Feature Engineering, Predictive Modeling, Model Evaluation

Frameworks & Libraries:
TensorFlow, Scikit-learn, Hugging Face Transformers, NumPy, Pandas, Matplotlib, Flask, OpenCV

GenAI & LLM:
RAG Pipelines, Prompt Engineering, Fine-Tuning, API Integration, Embedding Models, Resume Evaluation Systems, Transformer Models

Tools & Infrastructure:
Git, GitHub, Jupyter Notebook, VS Code, PyCharm, Redis, Celery

CAREER HIGHLIGHTS
• Built an AI-powered resume evaluation platform processing 100+ resumes/day with ~90% ranking accuracy.
• Evaluated and optimized 10+ LLM and transformer-based models for AI workflows.
• Improved AI evaluation speed by 20% while maintaining ~95% matching accuracy.
• Integrated Celery and Redis, improving platform reliability by 45%.
• Developed ML and GenAI systems across NLP, computer vision, predictive analytics, and automation.

EXPERIENCE

Data Scientist & Gen AI — Mirafra Technology (2025–Present)

- Developed a Flask-based AI resume evaluation platform processing 100+ resumes daily with ~90% candidate ranking accuracy.
- Evaluated and optimized 10+ LLM and transformer-based models using Hugging Face and cloud AI services to improve workflow performance.
- Improved model evaluation speed by 20% while maintaining ~95% matching accuracy.
- Integrated Celery and Redis to improve platform reliability and asynchronous task execution by 45%.
- Worked on AI workflows involving NLP, prompt engineering, transformer models, and automation.

Data Scientist & Operations — Mirafra Technology (2024–2025)

- Built machine learning models using Python and TensorFlow, improving prediction performance by 15%.
- Performed preprocessing, feature engineering, normalization, and model optimization on 100K+ records.
- Designed scalable data pipelines for data ingestion, validation, and analytics.
- Generated business insights through predictive analytics and model evaluation workflows.

DS & ML Intern — KVCH Pvt Ltd (2023)

- Built classification and predictive ML models using Python and Scikit-learn.
- Applied preprocessing and feature engineering techniques to improve model performance.
- Developed supervised learning workflows for analytics and business insights.

EDUCATION

M.Sc. in Data Science — Amity University, Jaipur (2024)
CGPA: 9.12/10

B.Sc. General — BSA College, Mathura (2022)

PROJECTS

RAG Pipeline for AI Model Evaluation
- Built a Retrieval-Augmented Generation (RAG) pipeline for evaluating AI systems, integrating transformer-based retrieval and benchmarking workflows.

Medical SLM Fine-Tuning
- Fine-tuned a Small Language Model for medical question-answering using instruction tuning and domain-specific datasets.

AI Resume Evaluation System
- Built an intelligent resume screening platform using NLP and transformer models for candidate-job matching.

Twitter Sentiment Analysis
- Developed an NLP pipeline using text preprocessing and classification models for sentiment prediction.

Loan Defaulter Analysis
- Built a predictive ML model on 250K+ records using feature engineering and Gradient Boosting.

Face Mask Detection in Android
- Developed a TensorFlow Lite Android application for real-time mask detection using computer vision.

Auto Completion using N-Gram
- Built an autocomplete system from scratch using statistical language modeling techniques.
""".strip()




# ── Core AI Functions ──────────────────────────────────────────────────

def analyze_job_match(job: JobListing, resume: str) -> MatchAnalysis:
    """
    Use Groq to analyze how well the candidate matches a job.
    Returns a structured MatchAnalysis with a 0-100 score.
    """
    console.print(f"  [pink]Analyzing match: {job.title} @ {job.company}...[/pink]")

    prompt = f"""
You are an expert AI recruiter.

Your task is to STRICTLY score how well a candidate matches a job.

You must be CRITICAL and realistic.
Do NOT inflate scores.

IMPORTANT:
Candidate profile:
- ~1 year internship experience
- Suitable for fresher to 1.5 years roles
- Strong in Generative AI, Data Science, ML, NLP
- Not suitable for Senior/Lead/Principal roles

STRICT RULES:
- Penalize jobs needing >2 years experience
- Penalize Senior/Lead/Staff/Principal roles
- Prioritize Data Scientist > GenAI > ML > NLP
- Give higher score to fresher/entry-level jobs

Scoring Rules:

90–100:
Excellent match.
Candidate has 80%+ required skills and highly relevant experience.

75–89:
Strong fit but missing some tools/domain experience.

60–74:
Moderate fit.
Has transferable skills but significant gaps.

40–59:
Weak fit.
Only partially relevant background.

0–39:
Poor fit.
Job is mostly unrelated.

Candidate Resume:
{resume}

Job Posting:

Title: {job.title}
Company: {job.company}
Location: {job.location}

Description:
{job.description[:3000]}

Evaluate:

1. Skill overlap
2. Years/level fit
3. Domain relevance
4. Project relevance
5. Tech stack match

IMPORTANT:
- Penalize missing required skills
- Do NOT give high scores just because both mention "AI"
- Freshers should NOT get 90+ for senior jobs
- Be realistic like a human recruiter

Return ONLY valid JSON:

{{
  "job_id": "{job.id}",
  "match_score": 0,
  "matched_skills": [],
  "missing_skills": [],
  "strengths": [],
  "concerns": [],
  "recommendation": "strong_apply",
  "reasoning": ""
}}
"""

    try:

        resp = get_client().chat.completions.create(
            model="llama-3.3-70b-versatile",  
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert technical recruiter. Return ONLY valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=600,
            temperature=0.2
        )
        raw = resp.choices[0].message.content.strip()


        # strip accidental markdown fences
        raw = re.sub(r"```json|```", "", raw).strip()

        try:
            json_match = re.search(
                r"\{.*\}",
                raw,
                re.DOTALL
            )

            if json_match:
                raw = json_match.group()
            try:      
                data = json.loads(raw)
            except json.JSONDecodeError:
                # escape raw newlines inside strings
                raw = raw.replace("\n", "\\n")
                data = json.loads(raw)        

        except Exception as e:
            console.print(
                f"[red]JSON parse failed:[/red] {e}"
            )
            console.print("\n[yellow]========= RAW MODEL OUTPUT =========[/yellow]")   
            console.print(raw[:5000])
            console.print("[yellow]====================================[/yellow]\n")     

            raise
        return MatchAnalysis(**data)
    
    except Exception as e:
        console.print(f"  [red]Match analysis failed:[/red] {e}")
        
        return MatchAnalysis(
            job_id=job.id,
            match_score=0,
            matched_skills=[],
            missing_skills=[],
            strengths=[],
            concerns=["Analysis failed"],
            recommendation="skip",
            reasoning=str(e),
        )

def tailor_application(
    job: JobListing, resume: str, match: MatchAnalysis
) -> TailoredApplication:
    """
    Use Groq to write a tailored resume summary + cover letter for a specific job.
    """
    console.print(f"  [dim]Writing application for {job.title} @ {job.company}...[/dim]")

    jd_info = extract_jd_structure(job.description)

    prompt = f"""
You are a senior recruiter and career coach.

Write a highly personalized, human-sounding cover letter.

STRICT RULES:
1. ONLY use experience explicitly present in the resume.
2. Mention EXACTLY 2–3 responsibilities from the job.
3. Connect resume evidence to job needs.
4. Mention at least 2 measurable achievements.
5. NEVER invent technologies or companies.
6. NEVER mention wrong company names.
7. DO NOT use phrases:
   - "I am thrilled to apply"
   - "I am excited for this opportunity"
   - "strong foundation in"
   - "passionate about"
   - "team player"
8. Avoid HR buzzwords.
9. Make it feel written specifically for THIS role.
10. Keep between 220–300 words.
11. Sound natural and professional.

BAD STYLE:
"I am thrilled to apply..."
"strong foundation in..."
"excited about the opportunity..."

GOOD STYLE:
"My experience building AI evaluation systems and optimizing transformer workflows aligns well with organizations building practical AI systems."

Candidate Resume:
{resume}

Company:
{job.company}

Role:
{job.title}

Required Skills:
{', '.join(jd_info["required_skills"])}

Preferred Skills:
{', '.join(jd_info["preferred_skills"])}

Responsibilities:
{chr(10).join('- ' + r for r in jd_info["responsibilities"][:3])}

Company Mission:
{jd_info["company_mission"]}

Technology Stack:
{', '.join(jd_info["tech_stack"])}

Experience Level:
{jd_info["experience_level"]}

Job Description:
{job.description[:3000]}

Match Analysis:
Score: {match.match_score}/100

Matched Skills:
{', '.join(match.matched_skills)}

Strengths:
{', '.join(match.strengths)}

Before finalizing internally check:
- Is company name correct?
- Does every claim exist in resume?
- Could this letter be reused for another company?
If yes → rewrite.

Return ONLY valid JSON:

{{
  "job_id": "{job.id}",
  "company": "{job.company}",
  "title": "{job.title}",
  "tailored_resume_summary": "",
  "cover_letter": "",
  "key_talking_points": [],
  "subject_line": ""
}}
"""  

    try:

        resp = get_client().chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",    
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert career coach. Return ONLY valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1200,
            temperature=0.1
        )

        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()

        try:
            json_match = re.search(
                r"\{.*\}",
                raw,
                re.DOTALL
            )

            if json_match:
                raw = json_match.group()
            try:    
                data = json.loads(raw)
            except json.JSONDecodeError:
                # escape raw newlines inside strings
                raw = raw.replace("\n", "\\n")
                data = json.loads(raw)   

        except Exception as e:
            console.print(
                f"[red]JSON parse failed:[/red] {e}"
            )
            console.print("\n[yellow]========= RAW MODEL OUTPUT =========[/yellow]")  
            console.print(raw[:5000])
            console.print("[yellow]====================================[/yellow]\n") 
            raise
        return TailoredApplication(**data)
    
    except Exception as e:
        console.print(f"  [red]Tailoring failed:[/red] {e}")
        return TailoredApplication(
            job_id=job.id,
            company=job.company,
            title=job.title,
            tailored_resume_summary="",
            cover_letter="",
            key_talking_points=[],
            subject_line=f"Application for {job.title}",
        )


def extract_skills_from_jd(description: str) -> list[str]:
    """Quick skill extraction from a job description using Groq."""
    prompt = f"""Extract the technical skills and tools mentioned in this job description.
                 Return ONLY a JSON array of strings. No markdown.
                 Job Description: {description[:3000]}"""

    try:
        resp = get_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "Extract only technical skills and return valid JSON array."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=200,
            temperature=0
        )
        raw = resp.choices[0].message.content.strip()

        return json.loads(raw)
    except Exception:
        return []
    

def extract_experience_level(description: str) -> dict:
    prompt = f"""
Extract experience requirements from this JD.

Return ONLY valid JSON:
{{
  "years_required": 0,
  "is_fresher_ok": false,
  "role_level": "fresher",
  "has_experience_requirement": false,
  "reasoning": ""
}}

Job Description:
{description[:2000]}
"""

    try:
        resp = get_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "Return only valid JSON. No markdown. No explanation."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=300,
            temperature=0
        )

        raw = resp.choices[0].message.content
        if not raw:
            return {
                "years_required": 0.0,
                "is_fresher_ok": True,
                "role_level": "entry",
                "has_experience_requirement": False,
                "reasoning": "Empty model response"
            }

        raw = raw.strip()
        raw = re.sub(r"```json|```", "", raw).strip()

        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            raw = json_match.group()

        data = json.loads(raw)

        yrs = data.get("years_required", 0)
        try:
            data["years_required"] = float(yrs)
        except (TypeError, ValueError):
            data["years_required"] = 0.0
        return data

    except Exception as e:  
        console.print(
            f"[red]Experience extraction failed:[/red] {e}"
        )

        console.print(
            "\n[yellow]RAW EXPERIENCE OUTPUT[/yellow]"
        )

        try:
            console.print(raw)
        except:
            pass

        return {
            "years_required": 0.0,
            "is_fresher_ok": True,
            "role_level": "entry",
            "has_experience_requirement": False,
            "reasoning": str(e)
        }                                     
        

def extract_jd_structure(description: str) -> dict:
    """
    Extract structured job information from raw JD.
    """

    prompt = f"""
Analyze this job description and extract information.

Return ONLY valid JSON.

Format:
{{
  "required_skills": [],
  "preferred_skills": [],
  "responsibilities": [],
  "company_mission": "",
  "tech_stack": [],
  "experience_level": ""
}}

Job Description:
{description[:4000]}
"""

    try:
        resp = get_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert recruiter. "
                        "Return ONLY valid JSON. "
                        "No markdown. No explanation."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=500,
            temperature=0
        )

        raw = (
            resp.choices[0]
            .message.content
            .strip()
        )

        # Remove markdown wrappers
        raw = re.sub(
            r"```json|```",
            "",
            raw
        ).strip()

        # Extract JSON safely
        json_match = re.search(r"\{.*\}",
            raw,
            re.DOTALL
        )

        if json_match:
            raw = json_match.group()

        data = json.loads(raw)

        return data

    except Exception as e:
        console.print(
            f"[red]JD extraction failed:[/red] {e}"
        )

        return {
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "company_mission": "",
            "tech_stack": [],
            "experience_level": ""
        }