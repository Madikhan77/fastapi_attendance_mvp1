import faiss
import numpy as np
import os
import pickle

# Define constants
FAISS_INDEX_PATH = "backend/ml_models/faiss_user_embeddings.index"
ID_MAP_PATH = "backend/ml_models/faiss_id_to_user_id.pkl"
EMBEDDING_DIMENSION = 512  # Should match ArcFace output dimension

# Initialize global variables
faiss_index = None
id_to_user_id_map = {}  # Maps internal FAISS contiguous IDs to our user_ids
next_faiss_id = 0  # Counter for next available FAISS ID

def _ensure_ml_models_dir_exists():
    """Ensures the directory for ML models exists."""
    os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)

def load_faiss_data():
    global faiss_index, id_to_user_id_map, next_faiss_id
    _ensure_ml_models_dir_exists() # Ensure directory exists before trying to load/create files

    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(ID_MAP_PATH):
        try:
            faiss_index = faiss.read_index(FAISS_INDEX_PATH)
            with open(ID_MAP_PATH, 'rb') as f:
                id_to_user_id_map = pickle.load(f)
            # next_faiss_id should be the count of items if IDs are 0-indexed and contiguous
            # or max_id + 1 if they are not strictly contiguous (though our add_embedding makes them so)
            next_faiss_id = faiss_index.ntotal # This assumes all loaded IDs are contiguous from 0
            if not id_to_user_id_map: # If map is empty, faiss_index.ntotal might be 0
                 next_faiss_id = 0
            elif max(id_to_user_id_map.keys(), default=-1) + 1 > next_faiss_id :
                 # If map has higher keys than faiss_index.ntotal implies (e.g. after partial deletion/rebuild issues)
                 # This logic might need refinement based on how robust the ID mapping is.
                 # For simplicity, we assume ntotal is the source of truth for next_faiss_id upon load.
                 # A more robust way if faiss_ids are not always 0..N-1 in map:
                 if id_to_user_id_map:
                     next_faiss_id = max(id_to_user_id_map.keys()) + 1
                 else:
                     next_faiss_id = 0


            print(f"FAISS data loaded. Index size: {faiss_index.ntotal}, Map size: {len(id_to_user_id_map)}, Next FAISS ID: {next_faiss_id}")
        except Exception as e:
            print(f"Warning: Could not load FAISS data (files exist but loading failed: {e}). Re-initializing.")
            faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
            id_to_user_id_map = {}
            next_faiss_id = 0
    else:
        print("FAISS data not found. Initializing new index and map.")
        faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        id_to_user_id_map = {}
        next_faiss_id = 0

def save_faiss_data():
    global faiss_index, id_to_user_id_map
    _ensure_ml_models_dir_exists() # Ensure directory exists before saving

    if faiss_index is None:
        print("Error: FAISS index is not initialized. Cannot save.")
        return

    try:
        faiss.write_index(faiss_index, FAISS_INDEX_PATH)
        with open(ID_MAP_PATH, 'wb') as f:
            pickle.dump(id_to_user_id_map, f)
        # print(f"FAISS data saved. Index size: {faiss_index.ntotal}, Map size: {len(id_to_user_id_map)}")
    except Exception as e:
        print(f"Error saving FAISS data: {e}")


def add_embedding(user_id: int, embedding: np.ndarray):
    global faiss_index, id_to_user_id_map, next_faiss_id

    if faiss_index is None:
        print("Error: FAISS index not initialized. Call load_faiss_data() first.")
        return None # Or raise an exception

    if not isinstance(embedding, np.ndarray):
        embedding = np.array(embedding) # Ensure it's a numpy array

    if embedding.ndim == 1:
        embedding = embedding.reshape(1, -1)
    
    if embedding.shape[1] != EMBEDDING_DIMENSION:
        raise ValueError(f"Embedding dimension mismatch. Expected {EMBEDDING_DIMENSION}, got {embedding.shape[1]}")

    embedding = embedding.astype(np.float32)

    current_faiss_id = next_faiss_id # This is the internal ID for FAISS
    
    faiss_index.add(embedding)
    id_to_user_id_map[current_faiss_id] = user_id
    next_faiss_id += 1
    
    save_faiss_data()
    return current_faiss_id


def search_embedding(query_embedding: np.ndarray, k: int = 1) -> list[tuple[int, float]]:
    global faiss_index, id_to_user_id_map

    if faiss_index is None or faiss_index.ntotal == 0:
        # print("FAISS index is empty or not initialized.")
        return []

    if not isinstance(query_embedding, np.ndarray):
        query_embedding = np.array(query_embedding)

    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)
    
    if query_embedding.shape[1] != EMBEDDING_DIMENSION:
        raise ValueError(f"Query embedding dimension mismatch. Expected {EMBEDDING_DIMENSION}, got {query_embedding.shape[1]}")

    query_embedding = query_embedding.astype(np.float32)

    # Determine the actual number of neighbors to search for (k_search)
    # k_search cannot exceed faiss_index.ntotal
    k_search = min(k, faiss_index.ntotal)
    if k_search == 0: # Should be caught by faiss_index.ntotal == 0 above, but as a safeguard
        return []

    distances, internal_indices = faiss_index.search(query_embedding, k_search)
    
    results = []
    for i in range(internal_indices.shape[1]): # Iterate through found neighbors for the first query
        internal_id = internal_indices[0, i]
        distance = distances[0, i]
        
        if internal_id == -1: # FAISS uses -1 for no valid neighbor found in that position
            continue

        user_id = id_to_user_id_map.get(internal_id)
        if user_id is not None:
            results.append((user_id, float(distance)))
        else:
            # This case should ideally not happen if the map and index are consistent
            print(f"Warning: Internal FAISS ID {internal_id} not found in id_to_user_id_map.")
            
    return results


def delete_embeddings_by_user_id(user_id_to_delete: int):
    global faiss_index, id_to_user_id_map, next_faiss_id
    
    if faiss_index is None or faiss_index.ntotal == 0:
        print("Cannot delete: FAISS index is empty or not initialized.")
        return 0

    faiss_ids_to_remove = [fid for fid, uid in id_to_user_id_map.items() if uid == user_id_to_delete]
    
    if not faiss_ids_to_remove:
        print(f"No embeddings found for user_id {user_id_to_delete}.")
        return 0

    # Rebuilding approach
    new_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
    new_id_map = {}
    current_new_id = 0
    
    # Iterate through all existing FAISS IDs from 0 to ntotal-1
    # This is more robust than iterating id_to_user_id_map.keys() if map keys aren't guaranteed contiguous
    num_removed = 0
    temp_vectors_to_add = []

    for old_faiss_id in range(faiss_index.ntotal):
        if old_faiss_id in faiss_ids_to_remove:
            num_removed +=1
            continue # Skip this vector
        
        # Reconstruct vector and add to new index
        vector = faiss_index.reconstruct(old_faiss_id) # reconstruct needs int ID
        if vector is not None: # Check if reconstruction was successful
            temp_vectors_to_add.append(vector.reshape(1, -1)) # Ensure 2D for add
            original_user_id = id_to_user_id_map[old_faiss_id] # Get original user_id
            new_id_map[current_new_id] = original_user_id
            current_new_id += 1
        else:
            # This indicates an issue with the index or the ID.
            print(f"Warning: Could not reconstruct vector for FAISS ID {old_faiss_id}. Skipping.")

    if temp_vectors_to_add:
        all_vectors_np = np.concatenate(temp_vectors_to_add, axis=0).astype(np.float32)
        new_index.add(all_vectors_np)

    faiss_index = new_index
    id_to_user_id_map = new_id_map
    next_faiss_id = current_new_id # The next ID is simply the count of items in the new map/index
    
    save_faiss_data()
    print(f"Removed {num_removed} embeddings for user_id {user_id_to_delete}. Index rebuilt.")
    return num_removed


# Initialize FAISS data on module load
try:
    load_faiss_data()
except Exception as e:
    print(f"FATAL: Failed to initialize vector_db module: {e}")
    # Depending on the application's error handling strategy, this might re-raise,
    # or functions above will fail if faiss_index is None.
    # For now, functions above have checks for None faiss_index.
    pass
