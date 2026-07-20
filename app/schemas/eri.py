from pydantic import BaseModel, Field
from typing import Optional

class ERILoginRequest(BaseModel):
    eriUserId: Optional[str] = Field(None, description="ERI user ID. If not provided, defaults to configured ERI_USER_ID.")
    password: Optional[str] = Field(None, description="Plaintext password. If not provided, defaults to configured ERI_PASSWORD.")

class ERILogoutRequest(BaseModel):
    pan: Optional[str] = Field("", description="Optional PAN for the taxpayer (ERI3) or empty (ERI2)")

class ERIAddClientRequest(BaseModel):
    pan: str = Field(..., max_length=10, description="Valid PAN of the taxpayer to add as client")
    dateOfBirth: str = Field(..., description="Date of birth of taxpayer in YYYY-MM-DD format")
    otpSourceFlag: str = Field(..., max_length=1, description="'E' for eFiling OTP, 'A' for Aadhaar OTP")

class ERIValidateClientOtpRequest(BaseModel):
    pan: str = Field(..., max_length=10, description="Valid PAN of the taxpayer")
    transactionId: str = Field(..., description="Transaction ID from the add-client response")
    otpSourceFlag: str = Field(..., max_length=1, description="'E' for eFiling OTP, 'A' for Aadhaar OTP")
    otp: str = Field(..., max_length=6, description="6-digit OTP code")
    validUpto: str = Field(..., description="ERI validity limit in YYYY-MM-DD format")

class ERIRegisterClientRequest(BaseModel):
    pan: str = Field(..., max_length=10)
    residentialStatusCd: str = Field(..., description="'RES' or 'NRI'")
    firstName: Optional[str] = None
    lastName: str
    midName: Optional[str] = None
    dateOfBirth: str = Field(..., description="Format YYYY-MM-DD")
    userGender: str = Field(..., description="'M', 'F', or 'T'")
    priMobileNum: str = Field(..., max_length=10)
    isdCd: str = Field("91", max_length=3)
    priMobBelongsTo: str = Field("1", max_length=2)
    priEmailRelationId: str = Field("1", max_length=2)
    priEmailId: str
    addrLine1Txt: str
    addrLine2Txt: str
    addrLine3Txt: Optional[str] = None
    addrLine4Txt: Optional[str] = None
    addrLine5Txt: Optional[str] = None
    pinCd: Optional[str] = None
    zipCd: Optional[str] = None
    stdCd: Optional[str] = None
    countryCd: str = "91"
    landlineNo: Optional[str] = None
    stateCd: Optional[str] = None
    foreignStateDesc: Optional[str] = None

class ERIValidateRegOtpRequest(BaseModel):
    pan: str = Field(..., max_length=10)
    smsTransactionId: str
    emailTransactionId: str
    mobileOtp: str = Field(..., max_length=6)
    emailOtp: str = Field(..., max_length=6)
    validUpto: str = Field(..., description="Format YYYY-MM-DD")

class ERIPrefillOtpRequest(BaseModel):
    pan: str = Field(..., max_length=10)
    assessmentYear: str = Field(..., max_length=4)
    otpSourceFlag: str = Field(..., max_length=1)

class ERIPrefillDataRequest(BaseModel):
    pan: str = Field(..., max_length=10)
    assessmentYear: str = Field(..., max_length=4)
    otpSourceFlag: str = Field(..., max_length=1)
    transactionId: str
    mobileOtp: str = Field(..., max_length=6)
    emailOtp: Optional[str] = None

class ERIUpdateVerModeRequest(BaseModel):
    pan: str = Field(..., max_length=10)
    ackNum: str = Field(...)
    ay: str = Field(...)
    formCode: str = Field(...)
    verMode: str = Field(..., description="LATER or ITRV")

class ERIGenerateEvcRequest(BaseModel):
    pan: str = Field(..., max_length=10)
    ackNum: str = Field(...)
    ay: str = Field(...)
    formCode: str = Field(...)
    verMode: str = Field(..., description="AADHAAR, BANKEVC, or DEMATEVC")

class ERIVerifyEvcRequest(BaseModel):
    pan: str = Field(..., max_length=10)
    ackNum: str = Field(...)
    ay: str = Field(...)
    formCode: str = Field(...)
    verMode: str = Field(...)
    transactionId: str
    otpValue: Optional[str] = None
    evcValue: Optional[str] = None

class ERIAcknowledgementRequest(BaseModel):
    pan: str = Field(..., max_length=10)
    ackNumber: str = Field(...)
