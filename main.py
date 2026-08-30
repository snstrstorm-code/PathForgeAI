from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import extractor

app = FastAPI()

class ResumeRequest(BaseModel):
    resume_text: str
    target_role: str = "Software Engineer"

@app.get("/")
def read_root():
    return {"message": "PathForge AI Backend is running!"}

@app.post("/analyze-resume")
def analyze_resume(payload: ResumeRequest):
    if not payload.resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume text cannot be empty.")
        
    try:
        result = extractor.analyze_resume_with_ai(
            resume_text=payload.resume_text, 
            target_role=payload.target_role
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    target_role: str = Form("Software Engineer")
):
    # Ensure uploaded file is a PDF
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported.")
    
    try:
        # 1. Read the uploaded file bytes
        file_bytes = await file.read()
        
        # 2. Extract plain text from PDF
        extracted_text = extractor.extract_text_from_pdf(file_bytes)
        
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from the PDF.")
            
        # 3. Pass extracted text to Gemini AI analysis
        result = extractor.analyze_resume_with_ai(
            resume_text=extracted_text, 
            target_role=target_role
        )
        
        return {
            "status": "success",
            "filename": file.filename,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
