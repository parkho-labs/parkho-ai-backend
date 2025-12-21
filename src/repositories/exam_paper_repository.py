from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from ..models.exam_paper import ExamPaper


class ExamPaperRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, exam_paper: ExamPaper) -> ExamPaper:
        """Create a new exam paper"""
        self.session.add(exam_paper)
        self.session.commit()
        self.session.refresh(exam_paper)
        return exam_paper

    def get_by_id(self, paper_id: int) -> Optional[ExamPaper]:
        """Get exam paper by ID"""
        return self.session.query(ExamPaper).filter(
            and_(ExamPaper.id == paper_id, ExamPaper.is_active == True)
        ).first()

    def get_all_active(self, limit: int = 50, offset: int = 0) -> List[ExamPaper]:
        """Get all active exam papers"""
        return (
            self.session.query(ExamPaper)
            .filter(ExamPaper.is_active == True)
            .order_by(desc(ExamPaper.year), desc(ExamPaper.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_year(self, year: int) -> List[ExamPaper]:
        """Get exam papers by year"""
        return (
            self.session.query(ExamPaper)
            .filter(and_(ExamPaper.year == year, ExamPaper.is_active == True))
            .order_by(desc(ExamPaper.created_at))
            .all()
        )

    def get_by_exam_name(self, exam_name: str) -> List[ExamPaper]:
        """Get exam papers by exam name"""
        return (
            self.session.query(ExamPaper)
            .filter(and_(ExamPaper.exam_name == exam_name, ExamPaper.is_active == True))
            .order_by(desc(ExamPaper.year), desc(ExamPaper.created_at))
            .all()
        )

    def get_by_exam_and_year(self, exam_name: str, year: int) -> List[ExamPaper]:
        """Get exam papers by exam name and year"""
        return (
            self.session.query(ExamPaper)
            .filter(
                and_(
                    ExamPaper.exam_name == exam_name,
                    ExamPaper.year == year,
                    ExamPaper.is_active == True
                )
            )
            .order_by(desc(ExamPaper.created_at))
            .all()
        )

    def search_papers(self, search_term: str) -> List[ExamPaper]:
        """Search exam papers by title or exam name"""
        search_filter = or_(
            ExamPaper.title.ilike(f"%{search_term}%"),
            ExamPaper.exam_name.ilike(f"%{search_term}%")
        )
        return (
            self.session.query(ExamPaper)
            .filter(and_(search_filter, ExamPaper.is_active == True))
            .order_by(desc(ExamPaper.year), desc(ExamPaper.created_at))
            .all()
        )

    def get_years_available(self) -> List[int]:
        """Get all unique years for which exam papers are available"""
        result = (
            self.session.query(ExamPaper.year)
            .filter(ExamPaper.is_active == True)
            .distinct()
            .order_by(desc(ExamPaper.year))
            .all()
        )
        return [row[0] for row in result]

    def get_exam_names_available(self) -> List[str]:
        """Get all unique exam names available"""
        result = (
            self.session.query(ExamPaper.exam_name)
            .filter(ExamPaper.is_active == True)
            .distinct()
            .order_by(ExamPaper.exam_name)
            .all()
        )
        return [row[0] for row in result]

    def get_paper_summary_stats(self) -> dict:
        """Get summary statistics of available papers"""
        total_papers = (
            self.session.query(ExamPaper)
            .filter(ExamPaper.is_active == True)
            .count()
        )

        years = self.get_years_available()
        exam_names = self.get_exam_names_available()

        return {
            "total_papers": total_papers,
            "available_years": years,
            "available_exams": exam_names,
            "year_range": {
                "earliest": min(years) if years else None,
                "latest": max(years) if years else None
            }
        }

    def update(self, exam_paper: ExamPaper) -> ExamPaper:
        """Update an existing exam paper"""
        self.session.commit()
        self.session.refresh(exam_paper)
        return exam_paper

    def delete(self, paper_id: int) -> bool:
        """Soft delete an exam paper by marking as inactive"""
        paper = self.get_by_id(paper_id)
        if paper:
            paper.is_active = False
            self.session.commit()
            return True
        return False

    def hard_delete(self, paper_id: int) -> bool:
        """Hard delete an exam paper from database"""
        paper = self.session.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
        if paper:
            self.session.delete(paper)
            self.session.commit()
            return True
        return False

    def activate_paper(self, paper_id: int) -> bool:
        """Reactivate a deactivated exam paper"""
        paper = self.session.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
        if paper:
            paper.is_active = True
            self.session.commit()
            return True
        return False

    def get_total_count(self) -> int:
        """Get total count of active exam papers"""
        return self.session.query(ExamPaper).filter(ExamPaper.is_active == True).count()

    def exists_by_title_and_year(self, title: str, year: int, exam_name: str) -> bool:
        """Check if an exam paper with same title, year and exam name already exists"""
        return (
            self.session.query(ExamPaper)
            .filter(
                and_(
                    ExamPaper.title == title,
                    ExamPaper.year == year,
                    ExamPaper.exam_name == exam_name,
                    ExamPaper.is_active == True
                )
            )
            .first()
        ) is not None