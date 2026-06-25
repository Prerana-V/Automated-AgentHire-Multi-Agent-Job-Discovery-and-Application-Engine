"""
tools/scraper.py — Free job scraping via JobSpy (no API key needed).
"""

from __future__ import annotations
import hashlib
import json
from typing import List, Dict, Any
from pathlib import Path
from rich.console import Console

console = Console()


def _make_id(title: str, company: str, url: str) -> str:
    """Create a stable unique ID for a job listing."""
    raw = f"{title}{company}{url}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def scrape_jobs(
    search_term: str,
    location: str = "Remote",
    results_wanted: int = 20,
    site_names: List[str] = None,
) -> List[Dict[str, Any]]:
    """
    Scrape jobs using jobspy (free, no API key).
    Falls back to mock data if jobspy isn't installed.

    Returns a list of raw job dicts.
    """
    if site_names is None:
        site_names = ["indeed", "linkedin"]

    try:
        from jobspy import scrape_jobs as _scrape

        console.print(
            f"[cyan]Scraping[/cyan] '{search_term}' in '{location}' "
            f"from {', '.join(site_names)}..."
        )
        df = _scrape(
            site_name=site_names,
            search_term=search_term,
            location="Remote, India",
            results_wanted=results_wanted,
            hours_old=168,
            country_indeed="India",
            is_remote=True,
        )


        df = df.drop_duplicates(subset=["job_url"])


        jobs = []
        source_counts = {}

        for _, row in df.iterrows():
            source = str(row.get("site", "unknown"))
            source_counts[source] = source_counts.get(source, 0) + 1

            desc = str(row.get("description", "")) or ""
            job = {
                "id": _make_id(
                    str(row.get("title", "")),
                    str(row.get("company", "")),
                    str(row.get("job_url", "")),
                ),
                "title": str(row.get("title", "Unknown")),
                "company": str(row.get("company", "Unknown")),
                "location": str(row.get("location", location)),
                "description": desc[:40000],
                "url": str(row.get("job_url", "")),
                "source": source,
                # "salary_min": _safe_int(row.get("min_amount")),
                # "salary_max": _safe_int(row.get("max_amount")),
                "posted_date": str(row.get("date_posted", "")),
                "job_type": str(row.get("job_type", "")),
            }
            jobs.append(job)

        console.print(f"[dim]Source counts: {source_counts}[/dim]")
        return jobs
    except ImportError:
        console.print(
            "[yellow]⚠ jobspy not installed — using mock data. "
            "Run: pip install python-jobspy[/yellow]"
        )
        return _mock_jobs(search_term, location)

    except Exception as e:
        console.print(f"[red]✗ Scraping error:[/red] {e}")
        return _mock_jobs(search_term, location)


def _safe_int(val: Any) -> int | None:
    try:
        return int(float(val)) if val and str(val) not in ("nan", "None", "") else None
    except (ValueError, TypeError):
        return None


def _mock_jobs(search_term: str, location: str) -> List[Dict[str, Any]]:
    """Return realistic mock jobs for testing without live scraping."""
    return [
        {
            "id": "mock001",
            "title": f"Gen AI Engineer - {search_term}",
            "company": "AI Vision Labs",
            "location": location,
            "description": (
                "We are hiring a Gen Ai Engineer to build predictive models and AI-driven solutions. "
                "Responsibilities include data preprocessing, feature engineering, "
                "model training, evaluation, and deployment. "
                "Required Skills: Python, Scikit-learn, Pandas, NumPy, "
                "Machine Learning, Data Visualization, Statistics. "
                "Preferred: Deep Learning, TensorFlow, NLP, model optimization. "
                "0-2 years experience accepted."
            ),
            "url": "https://example.com/job/mock001",
            "source": "indeed",
            "salary_min": 800000,
            "salary_max": 1500000,
            "posted_date": "2026-05-01",
            "job_type": "fulltime",
        },
        {
            "id": "mock002",
            "title": f"Data Scientist - {search_term}",
            "company": "DataNova Analytics",
            "location": location,
            "description": (
                "We are hiring a Data Scientist to build predictive models and AI-driven solutions. "
                "Responsibilities include data preprocessing, feature engineering, "
                "model training, evaluation, and deployment. "
                "Required Skills: Python, Scikit-learn, Pandas, NumPy, "
                "Machine Learning, Data Visualization, Statistics. "
                "Preferred: Deep Learning, TensorFlow, NLP, model optimization. "
                "0-2 years experience accepted."
            ),
            "url": "https://example.com/job/mock002",
            "source": "linkedin",
            "salary_min": 600000,
            "salary_max": 1800000,
            "posted_date": "2026-05-01",
            "job_type": "fulltime",
        },
        {
            "id": "mock003",
            "title": f"AI/ML Engineer - {search_term}",
            "company": "NeuralEdge Systems",
            "location": location,
            "description": (
                "Join our AI/ML engineering team to build intelligent systems using "
                "machine learning and Generative AI. "
                "You will work on NLP, computer vision, and LLM-based applications. "
                "Required Skills: Python, TensorFlow/PyTorch, Computer Vision, "
                "NLP, Transformers, Deep Learning. "
                "Preferred: Fine-tuning LLMs, model evaluation, APIs, Flask/FastAPI. "
                "Fresh graduates with strong project experience are welcome."
            ),
            "url": "https://example.com/job/mock003",
            "source": "naukri",
            "salary_min": 650000,
            "salary_max": 1800000,
            "posted_date": "2024-01-10",
            "job_type": "fulltime",
        },
    ]


def save_jobs(jobs: List[Dict], output_path: Path) -> None:
    """Save raw scraped jobs to JSON for debugging / re-runs."""
    with open(output_path, "w") as f:
        json.dump(jobs, f, indent=2, default=str)
    console.print(f"[dim]Saved {len(jobs)} raw jobs → {output_path}[/dim]")
