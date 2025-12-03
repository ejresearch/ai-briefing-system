"""
Node 1: Intake Backend Handler

Handles form submissions and writes user profiles to Google Sheets.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="AI Briefing System - Node 1 Intake")

# ============================================================================
# DATA MODELS
# ============================================================================

class UserProfile(BaseModel):
    """User profile schema matching Node 1 specification."""
    version: str
    email: EmailStr
    name: Optional[str] = None
    briefing_time: str  # HH:MM format
    topics: List[str]
    created_at: str  # ISO-8601 timestamp


# ============================================================================
# GOOGLE SHEETS INTEGRATION
# ============================================================================

class GoogleSheetsWriter:
    """
    Writes user profiles to Google Sheets.
    
    This is a placeholder implementation. In production, this would use:
    - Google Sheets API
    - Composio MCP integration
    - Or direct API calls
    """
    
    def __init__(self, spreadsheet_id: str = None):
        self.spreadsheet_id = spreadsheet_id
        self.profiles_file = Path("user_profiles.jsonl")
        
        # Create file if it doesn't exist
        if not self.profiles_file.exists():
            self.profiles_file.touch()
    
    def write_profile(self, profile: UserProfile) -> bool:
        """
        Write user profile to storage.
        
        In production, this would write to Google Sheets.
        For now, we store in JSONL format as a proof-of-concept.
        """
        try:
            # Append to JSONL file
            with open(self.profiles_file, 'a') as f:
                f.write(profile.json() + '\n')
            
            logger.info(f"Profile written for {profile.email}")
            return True
        
        except Exception as e:
            logger.error(f"Error writing profile: {str(e)}")
            return False
    
    def get_profiles(self) -> List[UserProfile]:
        """Retrieve all user profiles."""
        profiles = []
        
        try:
            if self.profiles_file.exists():
                with open(self.profiles_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            profiles.append(UserProfile.parse_raw(line))
        
        except Exception as e:
            logger.error(f"Error reading profiles: {str(e)}")
        
        return profiles


# Initialize sheets writer
sheets_writer = GoogleSheetsWriter()

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Serve the intake form."""
    return FileResponse("src/node1_intake_form.html", media_type="text/html")


@app.post("/api/intake")
async def create_intake(profile: UserProfile):
    """
    Create a new user profile.
    
    Validates the profile and writes it to Google Sheets.
    """
    try:
        # Validate email format
        if not profile.email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        # Validate briefing time format (HH:MM)
        try:
            hour, minute = profile.briefing_time.split(':')
            if not (0 <= int(hour) < 24 and 0 <= int(minute) < 60):
                raise ValueError("Invalid time")
        except:
            raise HTTPException(status_code=400, detail="Invalid briefing time format (use HH:MM)")
        
        # Validate topics
        if not profile.topics or len(profile.topics) == 0:
            raise HTTPException(status_code=400, detail="At least one topic must be selected")
        
        # Write to sheets
        success = sheets_writer.write_profile(profile)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save profile")
        
        return {
            "status": "success",
            "message": f"Profile created for {profile.email}",
            "profile": profile.dict()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profiles")
async def get_profiles():
    """Get all user profiles (admin endpoint)."""
    profiles = sheets_writer.get_profiles()
    return {
        "status": "success",
        "count": len(profiles),
        "profiles": [p.dict() for p in profiles]
    }


@app.get("/success")
async def success():
    """Success page after form submission."""
    return FileResponse("src/node1_success.html", media_type="text/html")


@app.get("/unsubscribe")
async def unsubscribe_page():
    """Unsubscribe page."""
    return FileResponse("src/node1_unsubscribe.html", media_type="text/html")


@app.get("/preferences")
async def preferences_page():
    """Preferences page."""
    return FileResponse("src/node1_preferences.html", media_type="text/html")


@app.post("/api/unsubscribe")
async def unsubscribe(data: dict):
    """Unsubscribe a user."""
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Mark as unsubscribed in the profiles file
    logger.info(f"Unsubscribe request for {email}")

    # For now, just log it - in production would update database
    return {"status": "success", "message": f"Unsubscribed {email}"}


@app.post("/api/preferences")
async def update_preferences(data: dict):
    """Update user preferences."""
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    topics = data.get("topics", [])
    briefing_time = data.get("briefing_time", "09:00")

    if not topics:
        raise HTTPException(status_code=400, detail="At least one topic is required")

    logger.info(f"Preferences update for {email}: {len(topics)} topics, time: {briefing_time}")

    # For now, just log it - in production would update database
    return {"status": "success", "message": "Preferences updated"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Node 1 - Intake",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
