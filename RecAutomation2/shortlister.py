import streamlit as st
import pandas as pd
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes
import io
import time
import re
import zipfile
import os
import requests

st.set_page_config(page_title="AI Resume Shortlister", layout="wide")
PRIMARY_COLOR = "#087ea4"

st.markdown(f"""
    <style>
    .stApp {{ background-color: #f5faff; }}
    .stButton>button, .stDownloadButton>button {{ background-color: {PRIMARY_COLOR}; color: white; border-radius: 8px; }}
    .card {{
        background: #fff;
        border-radius: 16px;
        box-shadow: 0 1px 8px #0002;
        padding: 18px 24px;
        margin-bottom: 24px;
        margin-top: 8px;
    }}
    .gpt-verdict {{
        background: #f6fbfa;
        border-left: 6px solid #3bb07b;
        padding: 12px 20px;
        margin-top: 12px;
        border-radius: 8px;
        font-size: 1.03rem;
        white-space: pre-line;
    }}
    .resume-raw {{
        color: #444;
        font-size: 0.98rem;
        background: #f8f9fb;
        border-radius: 8px;
        padding: 10px;
        margin-top: 14px;
        white-space: pre-wrap;
        overflow-x: auto;
        max-height: 300px;
    }}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div style="background:#eaf5fa;border-radius:10px;padding:15px 20px;font-size:1.15rem;"><b>AI Resume Shortlister</b>: Upload resumes and paste your job description below. Click "Shortlist!" to see ChatGPT verdicts for each candidate. Export all verdicts to Excel if needed.</div>', unsafe_allow_html=True)

# ---- Upload resumes ----
st.subheader("Step 1: Upload Resumes")
uploaded_files = st.file_uploader(
    "Upload resumes or ZIP (PDF/DOCX/JPG/PNG inside):",
    type=["pdf", "docx", "jpg", "jpeg", "png", "zip"],
    accept_multiple_files=True,
)

def extract_files(uploaded_files):
    resume_files = []
    errors = []
    for file in uploaded_files:
        if file.name.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(file) as z:
                    for zipinfo in z.infolist():
                        if zipinfo.filename.lower().endswith(('.pdf', '.docx', '.jpg', '.jpeg', '.png')):
                            with z.open(zipinfo) as resume:
                                resume_files.append({"filename": zipinfo.filename, "file": io.BytesIO(resume.read())})
            except Exception as e:
                errors.append(f"Failed to extract {file.name}: {e}")
        else:
            resume_files.append({"filename": file.name, "file": file})
    return resume_files, errors

resume_files, file_errors = extract_files(uploaded_files)
if file_errors:
    st.warning('\n'.join(file_errors))
st.write(f"Total resumes loaded: **{len(resume_files)}**")

# ---- Paste Job Description ----
st.subheader("Step 2: Paste Job Description")
job_desc = st.text_area("Paste the job description here 👇", height=200)

# ---- Extraction Functions ----
def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_image(image_file):
    image = Image.open(image_file)
    return pytesseract.image_to_string(image)

def extract_text_from_pdf_ocr(file):
    images = convert_from_bytes(file.read())
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img)
    return text

# ---- GPT Verdict API Call ----
def call_gpt_verdict_api(job_desc, resume_text, api_url="https://resume-backend-cyeb.onrender.com/gpt_verdict"):
    data = {
        "job_description": job_desc,
        "resume_text": resume_text,
    }
    try:
        response = requests.post(api_url, json=data, timeout=180)
        if response.ok:
            return response.json().get("result", "")
        else:
            return "Backend error"
    except Exception as e:
        return str(e)

# ---- PROCESSING ----
if st.button("Shortlist!"):
    if not resume_files or not job_desc:
        st.warning("Please upload resumes and paste the job description.")
    else:
        st.info("⏳ Processing resumes and getting GPT verdicts, please wait...")
        progress_bar = st.progress(0)
        extracted = []
        all_verdicts = []
        for i, item in enumerate(resume_files):
            filename = item['filename']
            file = item['file']
            text = ""
            try:
                if filename.lower().endswith(".pdf"):
                    text = extract_text_from_pdf(file)
                    if not text or len(text) < 50:
                        file.seek(0)
                        text = extract_text_from_pdf_ocr(file)
                elif filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    text = extract_text_from_image(file)
                elif filename.lower().endswith(".docx"):
                    text = extract_text_from_docx(file)
            except Exception as e:
                st.warning(f"Could not read {filename}: {e}")
                text = ""
            # Call GPT backend for each candidate
            with st.spinner(f"Analyzing {filename}..."):
                verdict = call_gpt_verdict_api(job_desc, text)
            extracted.append({"filename": filename, "resume_text": text, "gpt_verdict": verdict})
            all_verdicts.append({
                "Filename": filename,
                "GPT Verdict": verdict
            })
            progress_bar.progress((i + 1) / len(resume_files))
            time.sleep(0.02)
        progress_bar.empty()

        # Show all cards with verdicts
        st.success(f"Shortlisting complete! {len(extracted)} candidates analyzed.")
        for r in extracted:
            filename = r['filename']
            resume_text = r['resume_text']
            verdict = r['gpt_verdict']
            st.markdown(f'<div class="card">', unsafe_allow_html=True)
            st.markdown(f"**{filename}**", unsafe_allow_html=True)
            st.markdown(f'<div class="gpt-verdict">{verdict}</div>', unsafe_allow_html=True)
            with st.expander("Show Extracted Resume Text"):
                st.markdown(f'<div class="resume-raw">{resume_text[:2500] + ("..." if len(resume_text)>2500 else "")}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Export verdicts as Excel
        if all_verdicts:
            df_gpt = pd.DataFrame(all_verdicts)
            output = io.BytesIO()
            df_gpt.to_excel(output, index=False)
            st.download_button(
                label="Download All Verdicts as Excel",
                data=output.getvalue(),
                file_name="ai_shortlist_verdicts.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

st.markdown("---")
st.markdown("<center><small>Made with ❤️ for Modern HR & Recruitment. Data stays private.</small></center>", unsafe_allow_html=True)
