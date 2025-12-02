#!/usr/bin/env python3
"""
Quick test script for the AI Briefing System.

Usage:
    python test_briefing.py              # Preview briefing (no email)
    python test_briefing.py --send       # Generate and send email
    python test_briefing.py --check      # Just check services are running
"""

import os
import sys
import asyncio
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def check_env():
    """Check required environment variables."""
    required = ['OPENAI_API_KEY']
    optional = ['ARTICLE_SERVICE_URL', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'FROM_EMAIL']

    print("\n🔍 Checking environment...\n")

    missing = []
    for var in required:
        val = os.getenv(var)
        if val:
            print(f"  ✅ {var}: {'*' * 8}...{val[-4:]}")
        else:
            print(f"  ❌ {var}: NOT SET")
            missing.append(var)

    print()
    for var in optional:
        val = os.getenv(var)
        if val:
            if 'PASSWORD' in var or 'KEY' in var:
                print(f"  ✅ {var}: {'*' * 8}")
            else:
                print(f"  ✅ {var}: {val}")
        else:
            print(f"  ⚠️  {var}: not set (using default)")

    if missing:
        print(f"\n❌ Missing required env vars: {', '.join(missing)}")
        return False
    return True


async def check_services():
    """Check if Article Service is reachable."""
    import aiohttp

    url = os.getenv('ARTICLE_SERVICE_URL', 'http://localhost:8002')
    print(f"\n🔍 Checking Article Service at {url}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"  ✅ Article Service: {data.get('service')} v{data.get('version', '?')}")
                    print(f"     Sources: {data.get('sources_configured', '?')}")
                    return True
                else:
                    print(f"  ❌ Article Service returned {resp.status}")
                    return False
    except Exception as e:
        print(f"  ❌ Cannot reach Article Service: {e}")
        return False


async def preview_briefing():
    """Generate and preview a briefing without sending."""
    from node2_briefing_generator import BriefingGenerator, config
    from datetime import datetime, timedelta

    print("\n📰 Generating briefing preview...\n")

    generator = BriefingGenerator(config)

    # Load user
    profiles = generator.profile_loader.load_profiles()
    if not profiles:
        print("❌ No user profiles found. Add one to user_profiles.jsonl")
        return

    user = profiles[0]
    print(f"👤 User: {user.email}")
    print(f"📌 Topics: {', '.join(user.topics)}\n")

    # Fetch articles
    articles = await generator.article_fetcher.fetch_articles()
    articles = generator.article_fetcher.deduplicate(articles)
    articles = generator.article_fetcher.filter_recent(articles, hours=48)
    articles_by_source = generator.article_fetcher.group_by_source(articles)

    print(f"📥 Fetched {len(articles)} articles from {len(articles_by_source)} sources\n")

    # Process
    print("🤖 Processing with LLM...")
    processed = await generator.llm_processor.process_all_sites_parallel(
        articles_by_source, user.topics
    )
    print(f"   Processed: {len(processed)} articles\n")

    # Group for landscape
    processed_by_source = {}
    for a in processed:
        src = a.get("source", "Unknown")
        if src not in processed_by_source:
            processed_by_source[src] = []
        processed_by_source[src].append(a)

    # Generate sections
    print("📝 Generating Landscape...")
    landscape = await generator.llm_processor.generate_landscape(
        processed_by_source, user.topics, len(articles)
    )

    print("📝 Selecting Top 5...")
    top5 = await generator.llm_processor.select_top_5(processed, user.topics)

    print("📝 Generating Deep Dives...")
    deep_dives = await generator.llm_processor.generate_deep_dives(processed, user.topics)

    # Print results
    print("\n" + "=" * 70)
    print("YOUR AI BRIEFING - " + datetime.utcnow().strftime("%B %d, %Y"))
    print("=" * 70)

    print("\n## THE LANDSCAPE\n")
    print(landscape or "No landscape generated")

    print("\n## YOUR TOP 5\n")
    for i, a in enumerate(top5[:5], 1):
        print(f"{i}. {a.get('title')}")
        print(f"   {a.get('source')} | {a.get('url', '')[:50]}...")
        if a.get('why_selected'):
            print(f"   → {a.get('why_selected')}")
        print()

    print("## DEEP DIVES\n")
    for d in deep_dives[:3]:
        print(f"### {d.get('topic')}")
        print(f"*{d.get('hook')}*\n")
        print(d.get('analysis', '')[:500] + "...\n")

    print("=" * 70)
    print("✅ Preview complete!")


async def send_briefing():
    """Generate and send briefings to all users."""
    from node2_briefing_generator import BriefingGenerator, config

    print("\n📧 Generating and sending briefings...\n")

    generator = BriefingGenerator(config)
    results = await generator.run()

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)

    for r in results:
        status = "✅" if r.status == "success" else "❌"
        print(f"{status} {r.user_email}: {r.status}")
        if r.error:
            print(f"   Error: {r.error}")

    successful = sum(1 for r in results if r.status == "success")
    print(f"\nTotal: {len(results)} | Success: {successful} | Failed: {len(results) - successful}")


async def main():
    parser = argparse.ArgumentParser(description="Test AI Briefing System")
    parser.add_argument('--send', action='store_true', help='Send actual emails')
    parser.add_argument('--check', action='store_true', help='Only check services')
    args = parser.parse_args()

    print("\n🚀 AI Briefing System Test\n")

    # Check env
    if not check_env():
        sys.exit(1)

    # Check services
    service_ok = await check_services()

    if args.check:
        sys.exit(0 if service_ok else 1)

    if not service_ok:
        print("\n⚠️  Article Service not reachable. Starting local test anyway...\n")

    # Run test
    if args.send:
        await send_briefing()
    else:
        await preview_briefing()


if __name__ == "__main__":
    asyncio.run(main())
