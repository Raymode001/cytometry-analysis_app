import pandas as pd
from sqlalchemy.orm import sessionmaker
from schema import init_db, Project, Subject, Sample, CellCount
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self, db_url='sqlite:///cytometry.db'):
        self.engine = init_db(db_url)
        self.Session = sessionmaker(bind=self.engine)
    
    def load_csv(self, csv_path):
        """Load data from CSV file into the database."""
        try:
            # Read CSV file
            df = pd.read_csv(csv_path)
            session = self.Session()
            
            # Process each row
            for _, row in df.iterrows():
                # Create or get project
                project = session.query(Project).filter_by(project_id=row['project']).first()
                if not project:
                    project = Project(project_id=row['project'])
                    session.add(project)
                
                # Create or get subject
                subject = session.query(Subject).filter_by(subject_id=row['subject']).first()
                if not subject:
                    subject = Subject(
                        subject_id=row['subject'],
                        project_id=row['project'],
                        age=row.get('age', None),
                        sex=row.get('sex', None)
                    )
                    session.add(subject)
                
                # Create or get sample
                sample = session.query(Sample).filter_by(sample_id=row['sample']).first()
                if not sample:
                    sample = Sample(
                        sample_id=row['sample'],
                        subject_id=row['subject'],
                        condition=row['condition'],
                        treatment=row['treatment'],
                        response=row['response'],
                        sample_type=row['sample_type'],
                        time_from_treatment_start=row['time_from_treatment_start']
                    )
                    session.add(sample)
                
                # Create cell count
                cell_count = CellCount(
                    sample_id=row['sample'],
                    population=row['population'],
                    count=row['count']
                )
                session.add(cell_count)
            
            session.commit()
            logger.info(f"Successfully loaded data from {csv_path}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error loading data: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_cell_frequencies(self):
        """Calculate relative frequencies of cell populations for each sample."""
        session = self.Session()
        try:
            # Get all cell counts with sample information
            query = """
            SELECT 
                s.sample_id,
                s.sample_type,
                cc.population,
                cc.count,
                SUM(cc.count) OVER (PARTITION BY s.sample_id) as total_count,
                (cc.count * 100.0 / SUM(cc.count) OVER (PARTITION BY s.sample_id)) as percentage
            FROM samples s
            JOIN cell_counts cc ON s.sample_id = cc.sample_id
            ORDER BY s.sample_id, cc.population
            """
            
            result = session.execute(query)
            return pd.DataFrame(result.fetchall(), columns=[
                'sample_id', 'sample_type', 'population', 'count', 
                'total_count', 'percentage'
            ])
            
        finally:
            session.close()
    
    def get_response_comparison(self):
        """Compare cell populations between responders and non-responders."""
        session = self.Session()
        try:
            query = """
            SELECT 
                s.response,
                cc.population,
                cc.count,
                SUM(cc.count) OVER (PARTITION BY s.sample_id) as total_count,
                (cc.count * 100.0 / SUM(cc.count) OVER (PARTITION BY s.sample_id)) as percentage
            FROM samples s
            JOIN cell_counts cc ON s.sample_id = cc.sample_id
            WHERE s.sample_type = 'PBMC'
                AND s.condition = 'melanoma'
                AND s.treatment = 'tr1'
            ORDER BY s.response, cc.population
            """
            
            result = session.execute(query)
            return pd.DataFrame(result.fetchall(), columns=[
                'response', 'population', 'count', 'total_count', 'percentage'
            ])
            
        finally:
            session.close()
    
    def get_baseline_melanoma_tr1(self):
        """Get baseline melanoma tr1 samples with demographic information."""
        session = self.Session()
        try:
            query = """
            SELECT 
                p.project_id,
                s.response,
                sub.sex,
                COUNT(DISTINCT s.sample_id) as sample_count,
                COUNT(DISTINCT s.subject_id) as subject_count
            FROM samples s
            JOIN subjects sub ON s.subject_id = sub.subject_id
            JOIN projects p ON sub.project_id = p.project_id
            WHERE s.condition = 'melanoma'
                AND s.treatment = 'tr1'
                AND s.time_from_treatment_start = 0
                AND s.sample_type = 'PBMC'
            GROUP BY p.project_id, s.response, sub.sex
            ORDER BY p.project_id, s.response, sub.sex
            """
            
            result = session.execute(query)
            return pd.DataFrame(result.fetchall(), columns=[
                'project_id', 'response', 'sex', 'sample_count', 'subject_count'
            ])
            
        finally:
            session.close() 