from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    status: str
    is_admin: bool = False
    
    class Config:
        from_attributes = True

class UserCreditsResponse(BaseModel):
    wallet_balance: float
    total_generated: int
    
    class Config:
        from_attributes = True

class GenerationHistoryResponse(BaseModel):
    id: str
    run_id: str
    document_type: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class PlanResponse(BaseModel):
    id: int
    name: str
    price: float
    credits: int
    validity_days: int
    
    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    plan_id: int

class OrderResponse(BaseModel):
    id: str
    provider_order_id: str
    amount: float
    currency: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class CreditTransactionResponse(BaseModel):
    id: int
    amount: float
    transaction_type: str
    reference_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class DashboardResponse(BaseModel):
    user: UserResponse
    credits: UserCreditsResponse
    history: List[GenerationHistoryResponse]
    transactions: List[CreditTransactionResponse]
    plans: List[PlanResponse]

class AdminDashboardResponse(BaseModel):
    total_users: int
    active_users: int
    total_cards_generated: int
    total_revenue: float
    successful_payments: int
    pending_payments: int
    failed_payments: int
    outstanding_credits: float = 0.0

class AdminUserResponse(BaseModel):
    id: int
    name: str
    email: str
    status: str
    is_admin: bool
    created_at: datetime
    auth_provider: str = "email"
    avatar_url: Optional[str] = None
    wallet_balance: float = 0.0
    total_cards_generated: int = 0
    total_spent: float = 0.0
    paid_orders_count: int = 0
    last_active: Optional[datetime] = None
    credits: Optional[UserCreditsResponse] = None
    
    class Config:
        from_attributes = True

class AdminUserDetailResponse(BaseModel):
    user: AdminUserResponse
    recent_generations: List[GenerationHistoryResponse] = []
    recent_orders: List[OrderResponse] = []
    recent_transactions: List[CreditTransactionResponse] = []

class CreditAdjustmentRequest(BaseModel):
    amount: float
    reason: str

class AdminAuditLogResponse(BaseModel):
    id: int
    admin_id: int
    action: str
    target_user_id: Optional[int] = None
    details: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class SystemActivityItem(BaseModel):
    id: str
    activity_type: str # "generation", "registration", "credit_tx", "order", "admin_audit"
    title: str
    description: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    status: Optional[str] = "success"
    badge_label: str
    badge_type: str # "success", "info", "purple", "cyan", "danger"
    created_at: datetime

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
