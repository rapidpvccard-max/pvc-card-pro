from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from database import Base
import datetime
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True, index=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    status = Column(String, default="active")
    is_admin = Column(Boolean, default=False)

    credits = relationship("UserCredits", back_populates="user", uselist=False)
    generations = relationship("GenerationHistory", back_populates="user")
    orders = relationship("Order", back_populates="user")
    transactions = relationship("CreditTransaction", back_populates="user")

class UserCredits(Base):
    __tablename__ = "user_credits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    wallet_balance = Column(Float, default=5.0) # Default starting balance
    total_generated = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="credits")

class GenerationHistory(Base):
    __tablename__ = "generation_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"))
    run_id = Column(String, index=True)
    document_type = Column(String, default="aadhaar")
    status = Column(String) # "processing", "success", "failed"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    card_count = Column(Integer, default=1)

    user = relationship("User", back_populates="generations")

class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    price = Column(Float)
    credits = Column(Integer)
    validity_days = Column(Integer, default=365)
    active = Column(Boolean, default=True)
    stripe_price_id = Column(String, nullable=True) # Map to Stripe Price object

    orders = relationship("Order", back_populates="plan")

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"))
    provider_order_id = Column(String, unique=True, index=True) # e.g. cs_test_... (Stripe Checkout Session ID)
    provider_payment_id = Column(String, nullable=True) # e.g. pi_test_...
    plan_id = Column(Integer, ForeignKey("plans.id"))
    amount = Column(Float)
    currency = Column(String, default="USD")
    status = Column(String, default="pending") # pending, paid, failed, cancelled, refunded
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="orders")
    plan = relationship("Plan", back_populates="orders")

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float) # Positive for additions, Negative for deductions
    transaction_type = Column(String) # purchase, generation_usage, refund, admin_adjustment
    reference_id = Column(String) # UUID of run_id or order_id
    balance_after = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="transactions")

class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String) # e.g., 'credit_adjustment', 'user_deactivation', 'login'
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(String) # JSON payload containing reason, old state, new state, amount
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

