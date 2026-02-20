from pydantic import BaseModel

class AdminSetup(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    name: str | None = None
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Plugin(BaseModel):
    endpoint: str
    key: str
    type: str

class PluginManage(BaseModel):
    user_email: str = None
    plugin: Plugin

class PaymentRequest(BaseModel):
    tier: str
    lifetime: bool = False

class PaymentProcess(BaseModel):
    tier: str
    card_number: str
    expiry: str
    cvv: str

class OrchestrateRequest(BaseModel):
    query: str
    platform: str = "web"
    theme: str = "dark-pro"

class PluginRequest(BaseModel):
    provider: str
    key: str
    type: str

class AdminPluginRequest(PluginRequest):
    user_email: str | None = None

class ValidateRequest(BaseModel):
    provider: str
    key: str
