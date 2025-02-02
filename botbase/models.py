from sqlalchemy import JSON, TIMESTAMP, Column, Index, Integer, String, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ConversationEvent(Base):
    __tablename__ = "conversation_events"
    id = Column(Integer, primary_key=True)
    conv_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


Index("idx_conversation_events_conv_id", ConversationEvent.conv_id)
