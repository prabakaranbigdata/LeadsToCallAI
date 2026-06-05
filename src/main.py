import os
import logging
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

# Initialize logging for backend execution transparency
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SalesEngineMultiTenant")

app = FastAPI(title="Agentic Sales Engine - Live Notification Core")

# =====================================================================
# 1. LIVE CLIENT REGISTRY (Dynamic Notification Target Mapping)
# =====================================================================
CLIENT_REGISTRY = {
    "chennai_luxury_realty": {
        "business_name": "Chennai Luxury Realty",
        # UPDATE THIS: Replace with your actual mobile number (+91...) to receive test alerts!
        "owner_alert_number": "+919943876570", 
        "business_context": "Premium 3BHK/4BHK apartments and villa plots in OMR, ECR, and Adyar.",
        "expected_language": "English, Tamil, and Tanglish mixed conversational text."
    },
    "nungambakkam_ias_academy": {
        "business_name": "Nungambakkam IAS Coaching Center",
        "owner_alert_number": "+919943876570",
        "business_context": "UPSC, IAS, and TNPSC premium coaching programs with high enrollment values.",
        "expected_language": "English, Tamil, and regional inquiries."
    }
}

# =====================================================================
# 2. SCHEMA DEFINITION
# =====================================================================
class QualifiedLead(BaseModel):
    is_valid_lead: bool = Field(description="True if the user is explicitly inquiring about services, pricing, property, enrollment, or booking an appointment.")
    customer_name: str = Field(description="Extract the person's name if provided, otherwise 'Unknown'")
    intent_summary: str = Field(description="Brief summary of their exact requirement.")
    estimated_budget: str = Field(description="Extracted budget figures or financial bracket.")
    urgency: str = Field(description="Categorize strictly as: Immediate, Medium, or Low")

# =====================================================================
# 3. LIVE OUTBOUND PLUMBING (Twilio SMS Engine)
# =====================================================================
def send_live_sms_alert(to_number: str, message_body: str):
    try:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_number = os.environ.get("TWILIO_PHONE_NUMBER")
        
        if not account_sid or not auth_token or not from_number:
            logger.error("Twilio credentials missing.")
            return

        client = TwilioClient(account_sid, auth_token)
        
        # --- UPGRADED LIVE WHATSAPP PLUMBING ROUTE ---
        # We wrap the parameters with the 'whatsapp:' identifier block
        message = client.messages.create(
            body=message_body,
            from_=f"whatsapp:{from_number}", # Forces Twilio to route via WhatsApp network
            to=f"whatsapp:{to_number}"      # Delivers directly to your personal app screen
        )
        logger.info(f"Live WhatsApp message sent successfully! SID: {message.sid}")
        
    except Exception as e:
        logger.error(f"Failed to deliver alert: {str(e)}")

# =====================================================================
# 4. CORE PROCESSING LOGIC (Async Background Pipe)
# =====================================================================
def process_lead_with_gemini(client_id: str, client_info: dict, raw_message: str):
    try:
        ai_client = genai.Client()
        
        system_instruction = f"""
        You are a highly efficient inbound sales qualifying agent for '{client_info['business_name']}'. 
        Your business profile context is: {client_info['business_context']}
        The typical inquiry style is: {client_info['expected_language']}
        
        Analyze the incoming message and convert it strictly into the requested JSON schema structure.
        """
        
        prompt = f"Inbound message received:\n\"\"\"{raw_message}\"\"\""
        
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=QualifiedLead,
                temperature=0.1
            ),
        )
        
        lead_data = QualifiedLead.model_validate_json(response.text)
        logger.info(f"[{client_id}] Parsed Lead: {lead_data.customer_name} | Valid: {lead_data.is_valid_lead}")
        
        if lead_data.is_valid_lead:
            # Build an explicit, clean text format for standard SMS screens
            sms_payload = (
                f"🚨 SALES ENGINE ALERT 🚨\n\n"
                f"Client: {client_info['business_name']}\n"
                f"Lead: {lead_data.customer_name}\n"
                f"Intent: {lead_data.intent_summary}\n"
                f"Budget: {lead_data.estimated_budget}\n"
                f"Urgency: {lead_data.urgency.upper()}\n\n"
                f"⚡ Action: Reply within 5 mins!"
            )
            
            # Fire the live alert to the registered owner's mobile line
            target_phone = client_info['owner_alert_number']
            send_live_sms_alert(target_phone, sms_payload)
            
    except Exception as e:
        logger.error(f"[{client_id}] Critical parsing engine error: {str(e)}")

# =====================================================================
# 5. MULTI-TENANT ROUTER ENDPOINT
# =====================================================================
@app.post("/webhook/{client_id}")
async def inbound_webhook_router(client_id: str, request: Request, background_tasks: BackgroundTasks):
    if client_id not in CLIENT_REGISTRY:
        raise HTTPException(status_code=404, detail="Client registry target not found.")
        
    client_info = CLIENT_REGISTRY[client_id]
    
    try:
        body_bytes = await request.body()
        raw_message = body_bytes.decode("utf-8")
        if not raw_message:
            return Response(content="Empty payload", status_code=400)
    except Exception as e:
        return Response(content="Invalid encoding stream", status_code=400)
    
    # Hand off execution to background workers so webhook returns instantly (under 50ms)
    background_tasks.add_task(process_lead_with_gemini, client_id, client_info, raw_message)
    return Response(content="Event buffered by Sales Engine Pipe", status_code=200)

@app.get("/health")
async def health_check():
    return {"status": "operational", "active_profiles": len(CLIENT_REGISTRY)}