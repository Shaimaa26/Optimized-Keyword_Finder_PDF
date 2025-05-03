# pdf_utils.py
import PyPDF2

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
