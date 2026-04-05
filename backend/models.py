from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey,func
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Thread(Base):
    __tablename__ = "thread"

    thread_id = Column(String, primary_key = True,index = True)
    topic = Column(String,nullable= False)
    last_update = Column(String,nullable= False,server_default='update')
    num_slide = Column(Integer,nullable= False,server_default='5')
    img_path = Column(String, nullable=True)
    created_at = Column(DateTime,server_default=func.now())
    updated_at = Column(DateTime,server_default=func.now(),onupdate=datetime.utcnow)