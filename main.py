import pandas as pd
import io
import uuid
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from agent_logic import process_transactions

# Load environment variables from the .env file
load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Simple in-memory storage for the demo
results_storage = {}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main upload page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process", response_class=HTMLResponse)
async def create_upload_files(
    request: Request,
    qbo_transactions_file: UploadFile = File(...),
    qbo_accounts_file: UploadFile = File(...),
    qbo_classes_file: UploadFile = File(...)
):
    """Processes uploaded files and shows a results page."""
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return HTMLResponse(
            content="<h1>Server Configuration Error</h1><p>OPENAI_API_KEY is not set on the server.</p>", 
            status_code=500
        )

    try:
        transactions_df = pd.read_excel(qbo_transactions_file.file)
        accounts_df = pd.read_excel(qbo_accounts_file.file)
        classes_df = pd.read_excel(qbo_classes_file.file)

        result_df = process_transactions(transactions_df, accounts_df, classes_df, api_key)
        
        result_id = str(uuid.uuid4())
        results_storage[result_id] = result_df
        
        # --- CHANGE: Fill NaN with empty strings for a cleaner HTML preview ---
        preview_df = result_df.head(50).fillna('')
        results_html = preview_df.to_html(classes='table', index=False, border=0)
        
        return templates.TemplateResponse(
            "results.html", 
            {"request": request, "result_id": result_id, "results_table": results_html}
        )

    except Exception as e:
        return HTMLResponse(content=f"<h1>Error</h1><p>An error occurred: {e}</p>", status_code=500)
    
@app.get("/download/{result_id}")
async def download_file(result_id: str):
    """Serves the processed Excel file for download."""
    result_df = results_storage.get(result_id)
    if result_df is None:
        return HTMLResponse(content="<h1>Error</h1><p>Result not found or expired.</p>", status_code=404)

    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        result_df.to_excel(writer, index=False, sheet_name='Enriched_Transactions')
    
    # Optional: remove the result from memory after download
    # del results_storage[result_id]

    return StreamingResponse(
        iter([output_buffer.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=enriched_transactions.xlsx"}
    )