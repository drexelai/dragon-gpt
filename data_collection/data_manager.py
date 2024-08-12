from pinecone import Pinecone
from pinecone import ServerlessSpec
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import os
import time
import json
from dotenv import load_dotenv
from itertools import islice

load_dotenv("keys.env")

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
spec = ServerlessSpec(cloud="aws", region="us-east-1")
index_name = "dragongpt"
index = pc.Index(index_name)

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


def make_index(index_name):
    if index_name in pc.list_indexes().names():
        pc.delete_index(index_name)

    pc.create_index(
        name=index_name,
        dimension=384,
        metric="cosine",
        spec=spec
    )

    while not pc.describe_index(index_name).status['ready']:
        time.sleep(1)
    print("Index Created")

def create_vector(json_data):
    return embedding_model.encode(json.dumps(json_data))

def chunks(iterable, batch_size=200):
    """A helper function to break an iterable into chunks of size batch_size."""
    it = iter(iterable)
    chunk = tuple(islice(it, batch_size))
    while chunk:
        yield chunk
        chunk = tuple(islice(it, batch_size))

# json must be structured as a list of jsons [{"data": data, "url": url},...]
def upload_course_desc_files_to_index(filepath, batch_size=200):
    with open(filepath, "r") as f:
        data = json.load(f)

    pinecone_data = []
    for item in tqdm(data):
        data_item = item['data']
        vector = create_vector(data_item)
        metadata = {
            'Identifier': data_item['Identifier'],
            'Title': data_item['Title'],
            'Number_of_credits': data_item['Number_of_credits'],
            'Description': data_item['Description'],
            'College/Department': data_item['College/Department'],
            'Repeat Status': data_item['Repeat Status'],
            'Prerequisites': data_item['Prerequisites'],
            'url': item['url']
        }
        pinecone_data.append({
            'id': data_item['Identifier'],
            'values': vector,
            'metadata': metadata
        })

    for ids_vectors_chunk in chunks(pinecone_data, batch_size=batch_size):
        index.upsert(vectors=ids_vectors_chunk)

    print("Added data to index")
    print("Here is what the index looks like:")
    print(index.describe_index_stats())

def text_chunks(text, max_tokens=512):
    """Yield successive chunks of text."""
    words = text.split()
    for i in range(0, len(words), max_tokens):
        yield " ".join(words[i:i + max_tokens])

def upload_json_file_to_index(filepath, batch_size=200, max_tokens_per_chunk=512):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    pinecone_data = []
    for item in tqdm(data):
        header = item['Header']
        url = item['URL']
        text = item['Text']
        
        # Chunk the text into smaller pieces
        for chunk_index, text_chunk in enumerate(text_chunks(text, max_tokens=max_tokens_per_chunk)):
            vector = create_vector(text_chunk)
            metadata = {
                'Header': header,
                'URL': url,
                'Text_Chunk': text_chunk,
                'Chunk_Index': chunk_index
            }
            pinecone_data.append({
                'id': f"{url}_chunk_{chunk_index}",  # Unique ID for each chunk
                'values': vector,
                'metadata': metadata
            })

    for ids_vectors_chunk in chunks(pinecone_data, batch_size=batch_size):
        index.upsert(vectors=ids_vectors_chunk)

    print("Added data to index")
    print("Here is what the index looks like:")
    print(index.describe_index_stats())


def query_from_index(prompt:str, k=3)-> str:
        result = index.query(
            vector=embedding_model.encode(prompt).tolist(),
            top_k=k,
            include_metadata=True
        )
        matches = result['matches']
        print(matches)
        metadata_list = [match['metadata'] for match in matches]
        return "\n".join(str(metadata) for metadata in metadata_list)

if __name__ == "__main__":
    # upload_json_file_to_index(r'data_collection\tools\official_websites\official_website_files\scraped_text_data.json')
    pass