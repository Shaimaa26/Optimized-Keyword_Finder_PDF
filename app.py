import os
import pandas as pd
import PyPDF2
import streamlit as st
from io import BytesIO
import asyncio
import aiohttp
from concurrent.futures import ProcessPoolExecutor
import tempfile
import multiprocessing

# 💡 Fix for multiprocessing in Streamlit
multiprocessing.set_start_method("spawn", force=True)

from pdf_utils import extract_keywords_from_pdf


# --- Setup
st.set_page_config(page_title="Fast PDF Keyword Extractor", layout="centered")
st.title("⚡ Fast PDF Keyword Extractor")

# --- Sample Excel Generator
def generate_sample_excel():
    pdfs_data = pd.DataFrame({
        'Filename': ['https://www.example.com/sample1.pdf', 'https://www.example.com/sample2.pdf']
    })
    keywords_data = pd.DataFrame({
        'Keyword': ['voltage', 'current', 'temperature']
    })

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pdfs_data.to_excel(writer, sheet_name='PDFs', index=False)
        keywords_data.to_excel(writer, sheet_name='Keywords', index=False)
    output.seek(0)
    return output

st.markdown("### 📄 Download Sample Excel File")
st.download_button("📥 Download Sample Template", generate_sample_excel(), "sample_template.xlsx")

# --- PDF Downloader (Async)
async def download_pdf(session, url, path):
    try:
        async with session.get(url, timeout=30) as resp:
            if resp.status == 200:
                with open(path, 'wb') as f:
                    f.write(await resp.read())
                return True, url
            return False, url
    except Exception:
        return False, url

async def batch_download_pdfs(urls, folder):
    tasks = []
    async with aiohttp.ClientSession() as session:
        for idx, url in enumerate(urls):
            path = os.path.join(folder, f"{idx}.pdf")
            tasks.append(download_pdf(session, url, path))
        return await asyncio.gather(*tasks)

# --- PDF Parser (Parallel)
def extract_keywords_from_pdf(args):
    path, url, keywords = args
    try:
        reader = PyPDF2.PdfReader(path)
        text = ''
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + '\n'

        results = []
        lines = text.split('\n')
        for line in lines:
            lower = line.lower()
            for keyword in keywords:
                if keyword in lower:
                    start = lower.find(keyword)
                    cleaned = line[:start] + line[start+len(keyword):]
                    results.append({
                        'PDF Source': url,
                        'Keyword': keyword,
                        'Matched Line': line.strip(),
                        'Line Without Keyword': cleaned.strip()
                    })
                    break
        return results
    except Exception:
        return []

# --- Upload Excel
excel_file = st.file_uploader("📂 Upload your Excel file", type=["xlsx"])

if excel_file:
    try:
        pdf_df = pd.read_excel(excel_file, sheet_name="PDFs")
        keywords_df = pd.read_excel(excel_file, sheet_name="Keywords")
        urls = pdf_df['Filename'].dropna().astype(str).tolist()
        keywords = keywords_df['Keyword'].dropna().str.lower().tolist()

        with tempfile.TemporaryDirectory() as temp_dir:
            st.info(f"📡 Downloading {len(urls)} PDFs...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            download_results = loop.run_until_complete(batch_download_pdfs(urls, temp_dir))
            success_count = sum(1 for success, _ in download_results)
            st.success(f"✅ {success_count}/{len(urls)} PDFs downloaded.")

            # Prepare for multiprocessing
            st.info("🧠 Extracting keywords from PDFs...")
            input_data = []
            for idx, (success, url) in enumerate(download_results):
                if success:
                    input_data.append((os.path.join(temp_dir, f"{idx}.pdf"), url, keywords))

            with ProcessPoolExecutor() as executor:
                all_results = list(executor.map(extract_keywords_from_pdf, input_data))

            flat_results = [r for group in all_results for r in group]

            if flat_results:
                output_df = pd.DataFrame(flat_results)
                st.dataframe(output_df)

                output_file = "output_results.xlsx"
                output_df.to_excel(output_file, index=False, engine="openpyxl")

                with open(output_file, "rb") as f:
                    st.download_button("⬇️ Download Results", data=f, file_name="output_results.xlsx")
            else:
                st.warning("⚠️ No keyword matches found.")
    except Exception as e:
        st.error(f"❌ Error: {e}")
