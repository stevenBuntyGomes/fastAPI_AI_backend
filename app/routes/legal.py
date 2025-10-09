# app/routes/legal.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/legal", tags=["Legal"])

TERMS_HTML   = "<h1>Terms</h1><p>No tolerance for abusive/objectionable content. Violations may lead to removal and account suspension.</p>"
EULA_HTML    = "<h1>EULA</h1><p>Licensed, not sold. Use must comply with community guidelines.</p>"
CONTACT_HTML = "<h1>Contact</h1><p>Email: support@yourapp.com</p>"

@router.get("/terms", response_class=HTMLResponse)
async def terms():   return TERMS_HTML

@router.get("/eula", response_class=HTMLResponse)
async def eula():    return EULA_HTML

@router.get("/contact", response_class=HTMLResponse)
async def contact(): return CONTACT_HTML
