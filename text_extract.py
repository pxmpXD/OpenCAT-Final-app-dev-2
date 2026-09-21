


def extract_text(filepath, file_ext):
    file_ext = file_ext.lower()
    try:
        if file_ext == '.pdf':
            return _extract_pdf(filepath)
        elif file_ext == '.docx':
            return _extract_docx(filepath)
        elif file_ext == '.txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        else:
            return ''
    except Exception as e:
        
        print(f'Text extraction failed for {filepath}: {e}')
        return ''


def _extract_pdf(filepath):
    from pypdf import PdfReader
    reader = PdfReader(filepath)
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def _extract_docx(filepath):
    import docx
    doc = docx.Document(filepath)
    return '\n'.join(p.text for p in doc.paragraphs)
