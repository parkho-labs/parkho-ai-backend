import structlog
import json
import re
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Path as PathParam, Depends
from sqlalchemy.orm import Session

from ....services.gcp_service import GCPService
from ....config import get_settings
from ....core.database import get_db
from ..schemas import ExamAnswers, SubmitAttemptResponse, AttemptResultsResponse

logger = structlog.get_logger(__name__)
router = APIRouter()

settings = get_settings()
gcp_service = GCPService(settings)


def get_paper_metadata(filename: str, exam_type: str):
    year_match = re.search(r'20\d{2}', filename)
    year = int(year_match.group()) if year_match else 2024

    name = Path(filename).stem
    title = name.replace('-', ' ').replace('_', ' ')
    title = ' '.join(word.capitalize() for word in title.split())
    title = title.replace('Ugc Net', 'UGC NET').replace('Paper Ii', 'Paper II').replace('Solved Paper', '').strip()

    # Extract paper type (Paper I, Paper II, etc.)
    paper_type = None
    if 'paper ii' in title.lower() or 'paper-ii' in filename.lower():
        paper_type = "Paper II"
    elif 'paper i ' in title.lower() or 'paper-i' in filename.lower():
        paper_type = "Paper I"

    return {
        "filename": filename, 
        "title": title, 
        "year": year, 
        "exam_name": exam_type.replace('_', ' '),
        "paper_type": paper_type
    }


def get_paper_from_gcs(exam_type: str, filename: str):
    try:
        blob_path = f"pyq/{exam_type}/{filename}"
        if not gcp_service.check_file_exists(blob_path):
            return None

        with gcp_service.open_file_stream(blob_path) as f:
            if f is None:
                return None
            questions = json.load(f)

        metadata = get_paper_metadata(filename, exam_type)
        return {"questions": questions, **metadata, "total_questions": len(questions)}
    except:
        return None


def list_papers_from_gcs(exam_type: str = None):
    try:
        bucket = gcp_service.client.bucket(gcp_service.bucket_name)
        prefix = f"pyq/{exam_type}/" if exam_type else "pyq/"
        blobs = bucket.list_blobs(prefix=prefix)

        papers = []
        for blob in blobs:
            if blob.name.endswith('/'):
                continue

            path_parts = blob.name.split('/')
            if len(path_parts) >= 3:
                blob_exam_type = path_parts[1]
                blob_filename = path_parts[2]
                
                # Get full metadata
                metadata = get_paper_metadata(blob_filename, blob_exam_type)
                
                # Try to get actual question count from the file
                try:
                    paper_data = get_paper_from_gcs(blob_exam_type, blob_filename)
                    total_questions = len(paper_data.get("questions", [])) if paper_data else 0
                except:
                    total_questions = 100  # Default
                
                papers.append({
                    **metadata, 
                    "size": blob.size,
                    "total_questions": total_questions,
                    "total_marks": total_questions  # 1 mark per question
                })

        papers.sort(key=lambda x: (-(x.get('year', 0)), x.get('title', '')))
        return papers
    except:
        return []


@router.get("/")
async def list_all_papers(
    user_id: str = Query(None, description="Optional user ID to get attempt counts"),
    db: Session = Depends(get_db)
):
    papers = list_papers_from_gcs()
    
    # Add attempt counts if user_id provided
    if user_id:
        from ....models.user_attempt import UserAttempt
        for paper in papers:
            # Count attempts for this paper by checking filename in metadata
            attempts = db.query(UserAttempt).filter(
                UserAttempt.user_identifier == user_id,
                UserAttempt.answers.contains(f'"filename": "{paper["filename"]}"')
            ).count()
            paper["attempt_count"] = attempts
    
    return {"papers": papers, "total": len(papers)}


@router.get("/ugcnet")
async def list_ugcnet_papers(
    user_id: str = Query(None, description="Optional user ID to get attempt counts"),
    db: Session = Depends(get_db)
):
    papers = list_papers_from_gcs("UGC_NET")
    
    # Add attempt counts if user_id provided
    if user_id:
        from ....models.user_attempt import UserAttempt
        for paper in papers:
            attempts = db.query(UserAttempt).filter(
                UserAttempt.user_identifier == user_id,
                UserAttempt.answers.contains(f'"filename": "{paper["filename"]}"')
            ).count()
            paper["attempt_count"] = attempts
    
    return {"papers": papers, "total": len(papers)}


@router.get("/mpset")
async def list_mpset_papers(
    user_id: str = Query(None, description="Optional user ID to get attempt counts"),
    db: Session = Depends(get_db)
):
    papers = list_papers_from_gcs("MPSET")
    
    # Add attempt counts if user_id provided
    if user_id:
        from ....models.user_attempt import UserAttempt
        for paper in papers:
            attempts = db.query(UserAttempt).filter(
                UserAttempt.user_identifier == user_id,
                UserAttempt.answers.contains(f'"filename": "{paper["filename"]}"')
            ).count()
            paper["attempt_count"] = attempts
    
    return {"papers": papers, "total": len(papers)}


@router.get("/stats")
async def get_user_stats(
    user_id: str = Query(..., description="User ID to get statistics for"),
    db: Session = Depends(get_db)
):
    """
    Get user's PYQ practice statistics
    
    Returns:
    - papers_attempted: Total number of exam attempts
    - completed: Number of submitted/completed attempts
    - best_score: Highest percentage achieved
    - average_score: Average percentage across all attempts
    - day_streak: Consecutive days practiced
    """
    from ....models.user_attempt import UserAttempt
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    # Get all attempts for this user
    all_attempts = db.query(UserAttempt).filter(
        UserAttempt.user_identifier == user_id
    ).all()
    
    # Calculate stats
    papers_attempted = len(all_attempts)
    completed = sum(1 for a in all_attempts if a.is_submitted)
    
    # Best and average scores
    submitted_attempts = [a for a in all_attempts if a.is_submitted and a.percentage is not None]
    best_score = max((a.percentage for a in submitted_attempts), default=0)
    average_score = sum(a.percentage for a in submitted_attempts) / len(submitted_attempts) if submitted_attempts else 0
    
    # Day streak - count consecutive days with attempts
    if all_attempts:
        # Get unique days with attempts (sorted desc)
        attempt_dates = sorted(set(
            a.started_at.date() for a in all_attempts if a.started_at
        ), reverse=True)
        
        day_streak = 0
        if attempt_dates:
            current_date = datetime.now().date()
            expected_date = current_date
            
            for attempt_date in attempt_dates:
                if attempt_date == expected_date or attempt_date == expected_date - timedelta(days=1):
                    day_streak += 1
                    expected_date = attempt_date - timedelta(days=1)
                else:
                    break
    else:
        day_streak = 0
    
    return {
        "papers_attempted": papers_attempted,
        "completed": completed,
        "best_score": int(round(best_score)),
        "average_score": int(round(average_score)),
        "day_streak": day_streak,
        # New Stats
        "total_time_spent_minutes": int(sum(a.time_taken_seconds or 0 for a in submitted_attempts) / 60),
        "avg_time_per_paper_minutes": int((sum(a.time_taken_seconds or 0 for a in submitted_attempts) / len(submitted_attempts) / 60)) if submitted_attempts else 0,
        "total_questions_answered": sum(1 for a in submitted_attempts for q in (a.answers_dict or {}).get("submitted_answers", {})),
        "recent_scores": [
            {
                "date": a.submitted_at.isoformat() if a.submitted_at else a.started_at.isoformat(),
                "score": int(round(a.percentage or 0)),
                "paper": (a.answers_dict or {}).get("paper_title", "Unknown Paper")
            }
            for a in sorted(submitted_attempts, key=lambda x: x.submitted_at or x.started_at, reverse=True)[:5]
        ],
        "exam_breakdown": _get_exam_breakdown(all_attempts)
    }

def _get_exam_breakdown(attempts):
    """Helper to calculate stats per exam type (UGC NET, MPSET, etc.)"""
    breakdown = {}
    for a in attempts:
        if not a.is_submitted:
            continue
            
        data = a.answers_dict or {}
        exam_type = data.get("exam_type", "OTHER")
        
        if exam_type not in breakdown:
            breakdown[exam_type] = {"attempts": 0, "total_score": 0, "best_score": 0}
            
        breakdown[exam_type]["attempts"] += 1
        breakdown[exam_type]["total_score"] += (a.percentage or 0)
        breakdown[exam_type]["best_score"] = max(breakdown[exam_type]["best_score"], (a.percentage or 0))
    
    # Finalize averages
    for etype in breakdown:
        stats = breakdown[etype]
        if stats["attempts"] > 0:
            stats["average_score"] = int(round(stats["total_score"] / stats["attempts"]))
            stats["best_score"] = int(round(stats["best_score"]))
            del stats["total_score"]  # Clean up intermediate value
            
    return breakdown


@router.post("/papers/{exam_type}/{filename}/start")
async def start_exam_attempt(
    exam_type: str = PathParam(..., description="Exam type (UGC_NET, MPSET)"),
    filename: str = PathParam(..., description="Paper filename"),
    user_id: str = Query("anonymous", description="User identifier"),
    db: Session = Depends(get_db)
):
    """
    Start a new exam attempt for a GCS paper
    
    Creates an attempt record in the database and returns the attempt_id
    with questions (without answers)
    
    **Returns:**
    - `attempt_id`: Use this ID to submit answers later
    - `questions`: All questions without correct answers
    """
    try:
        # Get paper from GCS
        paper = get_paper_from_gcs(exam_type, filename)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        # Remove correct answers from questions
        questions = paper["questions"]
        if isinstance(questions, list):
            safe_questions = [{k: v for k, v in q.items() if k != "correct_answer"} for q in questions]
        else:
            safe_questions = []
        
        # Create attempt record in database (storing exam_type + filename as reference)
        from ....models.user_attempt import UserAttempt
        from datetime import datetime, timezone
        
        attempt = UserAttempt(
            paper_id=None,  # No paper_id since we're using GCS
            user_identifier=user_id,
            total_marks=paper.get("total_questions", len(questions)),
            started_at=datetime.now(timezone.utc)
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        
        # Store paper reference in attempt metadata
        attempt.answers = json.dumps({
            "exam_type": exam_type,
            "filename": filename,
            "paper_title": paper.get("title", ""),
            "started_questions": safe_questions
        })
        db.commit()
        
        logger.info("Started exam attempt from GCS", 
                   attempt_id=attempt.id,
                   exam_type=exam_type,
                   filename=filename,
                   user=user_id)
        
        return {
            "attempt_id": attempt.id,
            "exam_type": exam_type,
            "filename": filename,
            "paper_title": paper.get("title", ""),
            "paper_type": paper.get("paper_type"),
            "exam_name": paper.get("exam_name", exam_type),
            "year": paper.get("year", 2024),
            "total_questions": len(questions),
            "total_marks": paper.get("total_questions", len(questions)),
            "time_limit_minutes": 180,
            "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
            "questions": safe_questions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Start exam failed", 
                    exam_type=exam_type,
                    filename=filename,
                    user=user_id,
                    error=str(e), 
                    exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{exam_type}/{filename}")
async def get_paper(
    exam_type: str = PathParam(...),
    filename: str = PathParam(...),
    answers: bool = Query(False)
):
    paper = get_paper_from_gcs(exam_type, filename)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    questions = paper["questions"]
    if not answers and isinstance(questions, list):
        questions = [{k: v for k, v in q.items() if k != "correct_answer"} for q in questions]
        paper["questions"] = questions

    return paper


@router.post("/attempts/{attempt_id}/submit")
async def submit_exam_attempt(
    attempt_id: int = PathParam(..., description="Exam attempt ID"),
    answers: ExamAnswers = None,
    db: Session = Depends(get_db)
):
    """
    Submit exam answers and get results with score
    
    **Request Body:**
    ```json
    {
      "answers": {
        "36": "4",
        "91": "1",
        "95": "3"
      }
    }
    ```
    
    Note: Question IDs and answers are strings
    """
    try:
        from ....models.user_attempt import UserAttempt
        
        # Get attempt from database
        attempt = db.query(UserAttempt).filter(UserAttempt.id == attempt_id).first()
        if not attempt:
            raise HTTPException(status_code=404, detail=f"Exam attempt with ID {attempt_id} not found")
        
        if attempt.is_submitted:
            raise HTTPException(status_code=400, detail="This attempt has already been submitted")
        
        # Get paper info from attempt metadata
        attempt_data = json.loads(attempt.answers) if attempt.answers else {}
        exam_type = attempt_data.get("exam_type")
        filename = attempt_data.get("filename")
        
        if not exam_type or not filename:
            raise HTTPException(status_code=400, detail="Invalid attempt: missing paper reference")
        
        # Fetch paper from GCS to get correct answers
        paper = get_paper_from_gcs(exam_type, filename)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found in GCS")
        
        # Build correct answers dict (string keys) and normalize to letter format
        questions = paper["questions"]
        correct_answers = {}
        
        # Helper function to normalize answers
        def normalize_answer(ans):
            """Convert both '1'/'A' formats to unified format"""
            if not ans:
                return None
            ans = str(ans).strip().upper()
            # Map numbers to letters: 1→A, 2→B, 3→C, 4→D
            number_to_letter = {"1": "A", "2": "B", "3": "C", "4": "D"}
            return number_to_letter.get(ans, ans)
        
        for q in questions:
            q_id = str(q.get("id"))  # Convert to string
            correct_ans = q.get("correct_answer")
            if q_id and correct_ans:
                correct_answers[q_id] = normalize_answer(correct_ans)
        
        # Normalize user answers to letters too
        normalized_user_answers = {
            q_id: normalize_answer(ans) 
            for q_id, ans in answers.answers.items()
        }
        
        # Submit attempt with normalized answers
        # Don't use set_user_answers() as it overwrites metadata
        updated_data = attempt_data.copy()  # Preserve exam_type, filename, etc.
        updated_data["submitted_answers"] = normalized_user_answers
        updated_data["total_attempted"] = len(normalized_user_answers)
        attempt.answers = json.dumps(updated_data)
        
        score_data = attempt.calculate_score(correct_answers)
        
        # Update attempt
        attempt.score = score_data["score"]
        attempt.percentage = score_data["percentage"]
        attempt.is_completed = True
        attempt.is_submitted = True
        from datetime import datetime, timezone
        attempt.submitted_at = datetime.now(timezone.utc)
        
        if attempt.started_at:
            time_diff = datetime.now(timezone.utc) - attempt.started_at
            attempt.time_taken_seconds = int(time_diff.total_seconds())
        
        db.commit()
        db.refresh(attempt)
        
        # Normalize correct answers in questions for detailed results display
        normalized_questions = []
        for q in questions:
            q_copy = q.copy()
            q_copy["correct_answer"] = normalize_answer(q.get("correct_answer"))
            normalized_questions.append(q_copy)
        
        # Get detailed results with normalized questions
        detailed_results = attempt.get_detailed_results(normalized_questions)
        
        logger.info("Exam submitted successfully", 
                   attempt_id=attempt_id,
                   score=attempt.score)
        
        return {
            "attempt_id": attempt_id,
            "submitted": True,
            "score": attempt.score,
            "total_marks": attempt.total_marks,
            "percentage": attempt.percentage,
            "time_taken_seconds": attempt.time_taken_seconds,
            "display_time": attempt.display_time_taken,
            "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
            "paper_info": {
                "exam_type": exam_type,
                "filename": filename,
                "title": paper.get("title", ""),
                "exam_name": paper.get("exam_name", exam_type),
                "year": paper.get("year", 2024)
            },
            "detailed_results": detailed_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Submit exam failed", 
                    attempt_id=attempt_id, 
                    error=str(e), 
                    exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attempts/{attempt_id}/results")
async def get_attempt_results(
    attempt_id: int = PathParam(..., description="Exam attempt ID"),
    db: Session = Depends(get_db)
):
    """
    Get detailed results for a completed exam attempt
    
    Returns score, percentage, time taken, and question-by-question breakdown
    """
    try:
        from ....models.user_attempt import UserAttempt
        
        # Get attempt from database
        attempt = db.query(UserAttempt).filter(UserAttempt.id == attempt_id).first()
        if not attempt:
            raise HTTPException(status_code=404, detail=f"Exam attempt with ID {attempt_id} not found")
        
        if not attempt.is_submitted:
            raise HTTPException(status_code=400, detail="This attempt has not been submitted yet")
        
        # Get paper info from attempt metadata
        attempt_data = json.loads(attempt.answers) if attempt.answers else {}
        exam_type = attempt_data.get("exam_type")
        filename = attempt_data.get("filename")
        
        if not exam_type or not filename:
            raise HTTPException(status_code=400, detail="Invalid attempt: missing paper reference")
        
        # Fetch paper from GCS to get questions
        paper = get_paper_from_gcs(exam_type, filename)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found in GCS")
        
        questions = paper["questions"]
        
        # Normalize answers helper (same as submit)
        def normalize_answer(ans):
            """Convert both '1'/'A' formats to unified format"""
            if not ans:
                return None
            ans = str(ans).strip().upper()
            number_to_letter = {"1": "A", "2": "B", "3": "C", "4": "D"}
            return number_to_letter.get(ans, ans)
        
        # Normalize correct answers in questions for display
        normalized_questions = []
        for q in questions:
            q_copy = q.copy()
            q_copy["correct_answer"] = normalize_answer(q.get("correct_answer"))
            normalized_questions.append(q_copy)
        
        # Get detailed results
        detailed_results = attempt.get_detailed_results(normalized_questions)
        
        logger.info("Retrieved exam results", 
                   attempt_id=attempt_id,
                   score=attempt.score)
        
        return {
            "attempt_id": attempt_id,
            "score": attempt.score,
            "total_marks": attempt.total_marks,
            "percentage": attempt.percentage,
            "time_taken_seconds": attempt.time_taken_seconds,
            "display_time": attempt.display_time_taken,
            "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
            "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
            "paper_info": {
                "exam_type": exam_type,
                "filename": filename,
                "title": paper.get("title", ""),
                "exam_name": paper.get("exam_name", exam_type),
                "year": paper.get("year", 2024)
            },
            "detailed_results": detailed_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get results failed", 
                    attempt_id=attempt_id, 
                    error=str(e), 
                    exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))