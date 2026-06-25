"""
multiagent/workflow_manager.py — The main agentic loop. Coordinates: scraping → matching → tailoring → submitting → tracking.
"""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from config import (
    EnvConfig, JobListing, MatchAnalysis, ApplicationRecord,
    DEFAULT_SEARCH_QUERIES, DATA_DIR, JOBS_DIR, LOG_DIR
)
from tools.scraper import scrape_jobs, save_jobs
from tools.application_manager import submit_application, log_applications
from tools.tracker import push_to_notion
from multiagent.career_intelligence import analyze_job_match, tailor_application, load_resume, extract_skills_from_jd, extract_experience_level

console = Console()


class JobApplicationAgent:
    """
    Automated AgentHire application multiagent.

    Flow:
    1. Scrape jobs from multiple boards (free, no API key)
    2. Deduplicate against previously seen jobs
    3. Groq analyzes each job for match score
    4. Filter: only apply to jobs above MIN_MATCH_SCORE
    5. Groq writes tailored resume summary + cover letter
    6. Submit (SIMULATION MODE or live via Selenium)
    7. Track in Notion + local JSON log
    """

    def __init__(self, resume_path: str = "data/resumes/resume.txt"):
        self.resume = load_resume(resume_path)
        self.seen_ids: set[str] = self._load_seen_ids()
        self.session_records: List[ApplicationRecord] = []

    def run(self, search_queries: list = None) -> None:
        """Execute the full multiagent loop."""
        queries = search_queries or DEFAULT_SEARCH_QUERIES

        console.print(
            Panel.fit(
                f"[bold cyan]Automated AgentHire Application Agent[/bold cyan]\n"
                f"Mode: {'[yellow]SIMULATION MODE[/yellow]' if EnvConfig.DRY_RUN else '[pink]LIVE[/pink]'} | "
                f"Min Score: {EnvConfig.MIN_MATCH_SCORE} | "
                f"Max Apps: {EnvConfig.MAX_APPLICATIONS}",
                border_style="cyan",
            )
        )

        # ── Step 1: Scrape ──────────────────────────────────────────────
        all_jobs: List[JobListing] = []
        for q in queries:
            raw = scrape_jobs(
                search_term=q["title"],
                location=q.get("location", "Remote"),
                results_wanted=q.get("results", 20),
            )

            for j in raw:
                location = str(
                    j.get("location", "")
                ).lower()

                title = str(
                    j.get("title", "")
                ).lower()

                description = str(
                    j.get("description", "")
                ).lower()

                is_india_job = any(
                    kw in location for kw in [
                        "india", "remote", "bengaluru", "bangalore", "chennai",
                        "hyderabad", "pune", "delhi", "mumbai", "noida", "gurugram", "maharashtra",
                        "gurgaon", "remote, in", "india•remote", "wfh", "work from home",
                        "freelance", "lucknow", "jaipur"
                    ]
                )
                if not is_india_job:
                    continue
                        

                if j["id"] not in self.seen_ids:

                    # # Extract skills if description present
                    if j.get("description"):
                        j["skills_required"] = extract_skills_from_jd(j["description"])
                    job = JobListing(**j)
                    all_jobs.append(job)

        console.print(f"\n[bold]Found {len(all_jobs)} new jobs across all queries.[/bold]\n")

        if not all_jobs:
            console.print("[yellow]No new jobs to process. Exiting.[/yellow]")
            return

        # Save raw jobs for debugging
        save_jobs(
            [j.model_dump() for j in all_jobs],
            JOBS_DIR / f"jobs_{_ts()}.json",
        )

        # ── Step 2: Match & Filter ──────────────────────────────────────
        console.print("[bold cyan]Analyzing job matches...[/bold cyan]")

        matches: list[tuple[JobListing, MatchAnalysis]] = []

        MAX_YEARS_ALLOWED = 2
                
        for job in all_jobs:
            title = str(job.title or "").lower()
            description = str(job.description or "").lower()
            location = str(job.location or "").lower()

            exp_info = extract_experience_level(job.description or "")

            years_required_raw = exp_info.get("years_required", 0)
            try:
                years_required = float(years_required_raw)
            except (TypeError, ValueError):
                years_required = 0.0

            # Hard reject senior roles
            senior_keywords = [
                "senior", "lead", "principal", "staff", "sr",
                "manager", "director", "architect", "head of"
            ]
            if any(k in title for k in senior_keywords):
                continue

            # Hard reject jobs above 2 years
            if years_required > 2:
                continue

            # Keep junior/fresher/entry roles
            junior_keywords = [
                "junior", "jr", "fresher", "entry level", 
                "entry-level", "associate", "trainee", "graduate"
            ]

            ai_keywords = [
                "ai", "ml", "machine learning", "data scientist", "data science", "tensorflow", "pytorch", "transformer", "langgraph",
                "gen ai", "generative ai", "llm", "nlp", "deep learning", "dl", "artificial intelligence", "hugging face", "langchain",
                "computer vision", "analytics", "recommendation", "analyst", "mis analyst", "llm", "agents", "ai agent", "agentic"
            ]

            junior_match = any(k in title for k in junior_keywords) or any(
                k in description for k in junior_keywords
            )

            ai_match = any(k in title for k in ai_keywords) or any(
                k in description for k in ai_keywords
            )

            if not junior_match and not ai_match:
                continue

            match = analyze_job_match(job, self.resume)

            console.print(      
                f"[yellow]{job.source}[/yellow] | "
                f"Desc Length: {len(description)} | "
                f"AI Match: {ai_match} | "         
)

            console.print(
                f"[pink]Score:[/pink] {match.match_score} | "
                f"[blue]]Recommendation:[/blue] {match.recommendation} | "
                f"[magenta]Title:[/magenta] {job.title}")


            resume_keywords = [
                "python",
                "machine learning",
                "deep learning",
                "nlp",
                "llm",
                "transformer",
                "hugging face",
                "tensorflow",
                "pytorch",
                "generative ai",
                "data science",
                "computer vision",
                "bert",
                "fine tuning",
                "rag",
            ]

            resume_overlap = sum(keyword in description for keyword in resume_keywords)

            title_relevant = any(
                word in title
                for word in [
                    "ai",
                    "ml",
                    "machine learning",
                    "data scientist",
                    "gen ai",
                    "generative ai",
                    "llm",
                    "nlp",
                ]
            )

            if resume_overlap == 0 and not title_relevant:
                console.print(f"[orange]Low overlap skipped:[/orange] {job.title}")
                continue
                        
            if match.match_score >= EnvConfig.MIN_MATCH_SCORE:
                if job.description:
                    job.skills_required = (
                        extract_skills_from_jd(
                            job.description
                        )
                    )
                matches.append((job, match))
                status = (
                    f"[blue]✓ "
                    f"{match.match_score}/100 "
                    f"— {match.recommendation}[/blue]"
                )
            else:
                status = (
                    f"[orange]✗ "
                    f"{match.match_score}/100 "
                    f"— skipped[/orange]"
                )

            console.print(
                f"  {job.title} @ "
                f"{job.company}: {status}"
            )

        self._save_seen_ids()

        console.print(
            f"\n[bold]{len(matches)} jobs passed the {EnvConfig.MIN_MATCH_SCORE}+ threshold.[/bold]\n"
        )

        if not matches:
            console.print("[yellow]No jobs met the match threshold.[/yellow]")
            return

        # Sort by score descending, cap at max applications
        matches.sort(key=lambda x: x[1].match_score, reverse=True)
        matches = matches[: EnvConfig.MAX_APPLICATIONS]

        applied_companies=set()

        # ── Step 3: Tailor + Submit ─────────────────────────────────────
        console.print("[bold cyan]Tailoring applications and submitting...[/bold cyan]")

        for job, match in matches:

            company_key = (
                job.company.lower().strip()\
                
            )

            if company_key in applied_companies:
                console.print(
                    f"[yellow]Skipping duplicate company:[/yellow] "
                    f"{job.company}"
                )
                continue

            applied_companies.add(
                company_key
            )
            console.print(
                f"\n[bold]{job.title}[/bold] @ [bold]{job.company}[/bold] "
                f"(score: [green]{match.match_score}[/green])"
            )

            app = tailor_application(job, self.resume, match)
            record = submit_application(app, job.url, match.match_score)
            self.session_records.append(record)

        # Mark seen only after submit
        self.seen_ids.add(job.id)

        # ── Step 4: Track ───────────────────────────────────────────────
        log_path = LOG_DIR / "applications.json"
        log_applications(self.session_records, log_path)
        push_to_notion(self.session_records)

        # ── Step 5: Summary ─────────────────────────────────────────────
        self._print_summary()

    def _print_summary(self) -> None:
        """Print a rich table summary of this session."""
        table = Table(
            title="Session Summary",
            box=box.ROUNDED,
            border_style="cyan",
            show_lines=True,
        )
        table.add_column("Job Title", style="bold", max_width=30)
        table.add_column("Company", max_width=20)
        table.add_column("Score", justify="center")
        table.add_column("Status", justify="center")

        for r in self.session_records:
            score_color = "green" if r.match_score >= 80 else "yellow"
            status_color = "green" if r.status == "applied" else "red"
            table.add_row(
                r.title,
                r.company,
                f"[{score_color}]{r.match_score}[/{score_color}]",
                f"[{status_color}]{r.status}[/{status_color}]",
            )

        console.print("\n")
        console.print(table)

        applied = sum(1 for r in self.session_records if r.status == "applied")
        console.print(
            f"\n[bold green]✓ Done![/bold green] "
            f"Applied to {applied}/{len(self.session_records)} jobs this session.\n"
        )

    # ── Persistence ─────────────────────────────────────────────────────
    def _load_seen_ids(self) -> set[str]:
        path = DATA_DIR / "seen_ids.json"
        if path.exists():
            with open(path) as f:
                return set(json.load(f))
        return set()

    def _save_seen_ids(self) -> None:
        path = DATA_DIR / "seen_ids.json"
        with open(path, "w") as f:
            json.dump(list(self.seen_ids), f)


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
