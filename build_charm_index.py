import os
import json
import faiss
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

def build_charm_kb():
    manual_dir = "manuals"
    index_path = "charm_faiss.index"
    metadata_path = "charm_metadata.json"
    
    if not os.path.exists(manual_dir):
        print(f"Error: '{manual_dir}' directory not found.")
        return

    print("Initializing embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    documents = []
    metadata = []

    print("Collecting HTML files...")
    html_files = []
    for root, dirs, files in os.walk(manual_dir):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))

    if not html_files:
        print("No valid HTML documents found in the manuals folder.")
        return

    print(f"Parsing {len(html_files)} HTML files...")
    for filepath in tqdm(html_files):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator=' ', strip=True)
                if text:
                    documents.append(text)
                    metadata.append({
                        "source": filepath,
                        "text": text
                    })
        except Exception as e:
            pass

    print("Generating embeddings in batches...")
    embeddings = model.encode(documents, convert_to_numpy=True, show_progress_bar=True, batch_size=64)
    embeddings = embeddings.astype('float32')

    print("Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    print(f"Saving index to {index_path} and metadata to {metadata_path}...")
    faiss.write_index(index, index_path)
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print("Knowledge base successfully built and populated!")

if __name__ == "__main__":
    build_charm_kb()