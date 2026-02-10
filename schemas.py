from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class UserCreate(BaseModel):
    phone: str
    password: str
    email: Optional[str] = None
    name: str
    phonetwo: Optional[str] = None
    companyemail: Optional[str] = None
    fax: Optional[str] = None
    addressone: str
    addresstwo: Optional[str] = None
    area: str
    mailpw: Optional[str] = None
    orientation: Optional[str] = None
    billing: Optional[bool] = False
    coupon: Optional[bool] = False
    role: str = "customer"


class UserResponse(BaseModel):
    id: int
    role: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    phonetwo: Optional[str] = None
    area: Optional[str] = None
    billing: Optional[bool] = False
    coupon: Optional[bool] = False
    created: datetime

    class Config:
        from_attributes = True


class ChangePassword(BaseModel):
    name: str
    new_password: str


class UserLogin(BaseModel):
    phone: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


# ----------------------------------------------------------------------
# ASSAY RESULT SCHEMAS
# ----------------------------------------------------------------------

class AssayResultResponse(BaseModel):
    id: int
    customer: int
    customer_name: Optional[str] = None
    itemcode: str
    formcode: int
    collector: Optional[str] = None
    incharge: Optional[str] = None
    color: Optional[int] = None
    sampleweight: Optional[float] = None
    samplereturn: Optional[float] = None
    fwa: Optional[int] = None
    fwb: Optional[int] = None
    lwa: Optional[int] = None
    lwb: Optional[int] = None
    silverpct: Optional[int] = None
    resulta: Optional[float] = None
    resultb: Optional[float] = None
    preresult: Optional[float] = None
    loss: Optional[float] = None
    finalresult: Optional[float] = None
    created: datetime
    modified: datetime
    returndate: Optional[datetime] = None
    return_photo: Optional[str] = None

    class Config:
        from_attributes = True


# ----------------------------------------------------------------------
# CUSTOMER SCHEMAS
# ----------------------------------------------------------------------

class CustomerResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    area: Optional[str] = None
    billing: Optional[bool] = None
    coupon: Optional[bool] = None
    max_devices: Optional[int] = 1
    created: datetime
    total_assays: Optional[int] = None

    class Config:
        from_attributes = True


class PaginatedCustomers(BaseModel):
    items: list[CustomerResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ChangePasswordRequest(BaseModel):
    user_id: int
    new_password: str


class MaxDevicesUpdate(BaseModel):
    max_devices: int


class BatchReturnRequest(BaseModel):
    formcode: int
    collector: str
    incharge: str
    return_photo: Optional[str] = None


# ----------------------------------------------------------------------
# CALCULATOR SCHEMAS (Gold Alloy Calculator)
# ----------------------------------------------------------------------

class AlloyMaterial(BaseModel):
    name: str
    percentage: float
    weight: float


class CreateMixRecipeRequest(BaseModel):
    name: str
    input_weight: float
    input_purity: float
    desired_purity: float
    output_weight: float
    material_to_add: float
    material_type: str  # 'alloy' or 'pure_gold'
    total_alloy: float
    alloy_mix: List[AlloyMaterial]


class MixRecipeResponse(BaseModel):
    id: int
    user_id: int
    name: str
    input_weight: float
    input_purity: float
    desired_purity: float
    output_weight: float
    material_to_add: float
    material_type: str
    total_alloy: float
    alloy_mix: List[AlloyMaterial]
    created: datetime

    class Config:
        from_attributes = True
