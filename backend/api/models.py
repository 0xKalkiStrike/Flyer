from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from .db import Base

class UploadHistory(Base):
    __tablename__ = "upload_history"

    flyer_id = Column(Integer, primary_key=True, index=True)
    flyer_name = Column(String(255), nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(String(255), nullable=True)

class WebsiteVerificationData(Base):
    __tablename__ = "website_verification_data"

    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(String(512), nullable=False)
    login_used = Column(Boolean, default=False)
    flyer_id = Column(Integer, ForeignKey("upload_history.flyer_id"))

class ProductVerificationResult(Base):
    __tablename__ = "product_verification_results"

    id = Column(Integer, primary_key=True, index=True)
    flyer_id = Column(Integer, ForeignKey("upload_history.flyer_id"))
    product_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    issue_type = Column(String(100), nullable=True)
    product_url = Column(String(512), nullable=True)
    screenshot_path = Column(String(512), nullable=True)
    verification_timestamp = Column(DateTime(timezone=True), server_default=func.now())