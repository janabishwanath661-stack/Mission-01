from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./topicLens.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id = Column(String, primary_key=True, index=True)
    topic = Column(String, index=True)
    status = Column(String, default="pending")
    results = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_results(job_id: str, topic: str, data: dict):
    db = SessionLocal()
    try:
        job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
        if job:
            job.status = "completed"
            job.results = json.dumps(data)
            job.completed_at = datetime.utcnow()
        else:
            job = SearchJob(
                id=job_id,
                topic=topic,
                status="completed",
                results=json.dumps(data),
                completed_at=datetime.utcnow()
            )
            db.add(job)
        db.commit()
    finally:
        db.close()


def get_job(job_id: str) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
        if job:
            return {
                "id": job.id,
                "topic": job.topic,
                "status": job.status,
                "results": json.loads(job.results) if job.results else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }
        return None
    finally:
        db.close()


def create_job(job_id: str, topic: str):
    db = SessionLocal()
    try:
        job = SearchJob(id=job_id, topic=topic, status="pending")
        db.add(job)
        db.commit()
    finally:
        db.close()
