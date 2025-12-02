"""
Node 2 API - Web interface for triggering briefings.

Endpoints:
- POST /generate - Generate and send briefings
- POST /generate/{email} - Generate for specific user
- GET /preview/{email} - Preview briefing without sending
- GET /health - Health check
"""

import os
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from node2_briefing_generator import (
    BriefingGenerator,
    Config,
    config,
    UserProfile,
    Briefing,
    Landscape,
    DeepDive,
    ProcessedArticle
)

app = FastAPI(
    title="AI Briefing Generator",
    version="1.0.0",
    description="Generate personalized AI news briefings"
)

# Store for background job status
job_status = {"running": False, "last_run": None, "last_result": None}


class GenerateRequest(BaseModel):
    """Request body for generate endpoint."""
    email: Optional[str] = None  # If None, generate for all users
    send_email: bool = True


class GenerateResponse(BaseModel):
    """Response from generate endpoint."""
    status: str
    message: str
    users_processed: int = 0
    successful: int = 0
    failed: int = 0


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "service": "AI Briefing Generator",
        "job_running": job_status["running"],
        "last_run": job_status["last_run"],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate_briefings(
    request: GenerateRequest = GenerateRequest(),
    background_tasks: BackgroundTasks = None
):
    """
    Generate and send briefings.

    - If email is provided, generate for that user only
    - If email is None, generate for all users
    """
    if job_status["running"]:
        raise HTTPException(status_code=409, detail="A job is already running")

    job_status["running"] = True
    job_status["last_run"] = datetime.utcnow().isoformat() + "Z"

    try:
        generator = BriefingGenerator(config)
        results = await generator.run()

        successful = sum(1 for r in results if r.status == "success")
        failed = len(results) - successful

        job_status["last_result"] = {
            "users": len(results),
            "successful": successful,
            "failed": failed
        }

        return GenerateResponse(
            status="completed",
            message=f"Generated briefings for {len(results)} users",
            users_processed=len(results),
            successful=successful,
            failed=failed
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        job_status["running"] = False


@app.get("/preview/{email}", response_class=HTMLResponse)
async def preview_briefing(email: str):
    """
    Preview a briefing for a specific user without sending email.
    Returns the HTML that would be sent.
    """
    generator = BriefingGenerator(config)

    # Load profiles and find user
    profiles = generator.profile_loader.load_profiles()
    user = next((p for p in profiles if p.email == email), None)

    if not user:
        raise HTTPException(status_code=404, detail=f"User {email} not found")

    # Fetch and process articles
    from datetime import timedelta
    since_date = (datetime.utcnow() - timedelta(hours=48)).strftime("%Y-%m-%d")
    articles = await generator.article_fetcher.fetch_articles(since_date=since_date)
    articles = generator.article_fetcher.deduplicate(articles)
    articles = generator.article_fetcher.filter_recent(articles, hours=48)
    articles_by_source = generator.article_fetcher.group_by_source(articles)

    # Process with LLM
    processed = await generator.llm_processor.process_all_sites_parallel(
        articles_by_source, user.topics
    )

    if not processed:
        raise HTTPException(status_code=500, detail="No articles could be processed")

    # Group for landscape
    processed_by_source = {}
    for a in processed:
        src = a.get("source", "Unknown")
        if src not in processed_by_source:
            processed_by_source[src] = []
        processed_by_source[src].append(a)

    # Generate all sections
    landscape = await generator.llm_processor.generate_landscape(
        processed_by_source, user.topics, len(articles)
    )
    top5 = await generator.llm_processor.select_top_5(processed, user.topics)
    deep_dives = await generator.llm_processor.generate_deep_dives(processed, user.topics)

    # Build briefing
    briefing = Briefing(
        landscape=Landscape(content=landscape or ""),
        top_5=[
            ProcessedArticle(
                source=a.get("source", ""),
                url=a.get("url", ""),
                title=a.get("title", ""),
                summary=a.get("summary", ""),
                relevance=a.get("relevance", 0),
                keywords=a.get("keywords", []),
                why_selected=a.get("why_selected", ""),
                rank=i + 1
            )
            for i, a in enumerate(top5[:5])
        ],
        deep_dives=[
            DeepDive(
                topic=d.get("topic", ""),
                hook=d.get("hook", ""),
                analysis=d.get("analysis", ""),
                related_articles=d.get("related_articles", [])
            )
            for d in deep_dives[:3]
        ],
        articles_analyzed=len(processed),
        sources_count=len(articles_by_source)
    )

    # Render HTML
    briefing_date = datetime.utcnow().strftime("%B %d, %Y")
    html = generator.email_sender.compose_briefing_email(
        config.template_path, user, briefing, briefing_date
    )

    return html


@app.get("/users")
async def list_users():
    """List all registered users."""
    generator = BriefingGenerator(config)
    profiles = generator.profile_loader.load_profiles()

    return {
        "count": len(profiles),
        "users": [
            {
                "email": p.email,
                "name": p.name,
                "topics": p.topics,
                "briefing_time": p.briefing_time
            }
            for p in profiles
        ]
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8003))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
