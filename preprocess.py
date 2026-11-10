import re
import os


def strip_gutenberg(text):
    start = re.search(r'\*\*\* ?START OF (THIS |THE )?PROJECT GUTENBERG', text, re.IGNORECASE)
    if start:
        after = text[start.end():]
        newline = after.find('\n')
        text = after[newline + 1:] if newline != -1 else after

    end = re.search(r'\*\*\* ?END OF (THIS |THE )?PROJECT GUTENBERG', text, re.IGNORECASE)
    if end:
        text = text[:end.start()]

    return text.strip()


def clean_text(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def make_text_id(filepath):
    name = os.path.splitext(os.path.basename(filepath))[0]
    return re.sub(r'[^\w]', '_', name)[:50].lower().strip('_')


def chunk_text(text, text_id, chunk_words=1000, overlap_words=200):
    """
    Sliding-window word-level chunking with overlap.
    Step = chunk_words - overlap_words so consecutive chunks share ~200 words,
    preventing a belief statement from being cut at a boundary.
    """
    words = text.split()
    step  = max(chunk_words - overlap_words, 1)
    chunks = []
    chunk_n = 0

    for start in range(0, len(words), step):
        end = min(start + chunk_words, len(words))
        word_count = end - start
        if word_count < 50:          # skip tiny trailing fragment
            break
        chunk_n += 1
        chunks.append({
            'chunk_id':   f"{text_id}_c{chunk_n:04d}",
            'text_id':    text_id,
            'text':       ' '.join(words[start:end]),
            'word_count': word_count,
        })
        if end >= len(words):
            break

    return chunks


def load_and_preprocess(filepath, chunk_words=1000, overlap_words=200):
    with open(filepath, encoding='utf-8', errors='replace') as f:
        raw = f.read()

    text    = strip_gutenberg(raw)
    text    = clean_text(text)
    text_id = make_text_id(filepath)
    chunks  = chunk_text(text, text_id, chunk_words, overlap_words)
    return chunks, text_id
