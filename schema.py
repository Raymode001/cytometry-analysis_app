from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Project(Base):
    __tablename__ = 'projects'
    
    project_id = Column(String, primary_key=True)
    name = Column(String)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    subjects = relationship("Subject", back_populates="project")

class Subject(Base):
    __tablename__ = 'subjects'
    
    subject_id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey('projects.project_id'))
    age = Column(Integer)
    sex = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="subjects")
    samples = relationship("Sample", back_populates="subject")

class Sample(Base):
    __tablename__ = 'samples'
    
    sample_id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey('subjects.subject_id'))
    condition = Column(String)  # e.g., melanoma, bladder_cancer
    treatment = Column(String)  # e.g., tr1
    response = Column(String)   # 'y' for responder, 'n' for non-responder
    sample_type = Column(String)  # e.g., PBMC
    time_from_treatment_start = Column(Integer)  # in days
    created_at = Column(DateTime, default=datetime.utcnow)
    
    subject = relationship("Subject", back_populates="samples")
    cell_counts = relationship("CellCount", back_populates="sample")

class CellCount(Base):
    __tablename__ = 'cell_counts'
    
    id = Column(Integer, primary_key=True)
    sample_id = Column(String, ForeignKey('samples.sample_id'))
    population = Column(String)  # e.g., b_cell, cd8_t_cell
    count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sample = relationship("Sample", back_populates="cell_counts")

# Create database engine
def init_db(db_url='sqlite:///cytometry.db'):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine 