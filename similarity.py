import numpy as np

def cosine_similarity(vec1, vec2):
    """
    Take two vectors and cosine similarity is calculated and returned as a value.

    Parameters:
    vec1 (list or np.ndarray): First vector
    vec2 (list or np.ndarray): Second vector

    Returns:
    float: Cosine similarity between the two vectors
    """
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    dot_product = np.dot(vec1, vec2)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)

    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0

    return dot_product / (norm_vec1 * norm_vec2)