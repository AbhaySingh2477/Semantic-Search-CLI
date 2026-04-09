import sys
from embedding import get_embedding
from similarity import cosine_similarity

def sim_command(text1, text2):
    vec1 = get_embedding(text1)
    vec2 = get_embedding(text2)

    score = cosine_similarity(vec1, vec2)
    print(f"Similarity Score: {score:.4f}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py sim <text1> <text2>")
        return

    command = sys.argv[1]

    if command == "sim":
        if len(sys.argv) != 4:
            print("Usage: python main.py sim <text1> <text2>")
            return

        text1 = sys.argv[2]
        text2 = sys.argv[3]

        sim_command(text1, text2)

    else:
        print("Unknown command")

if __name__ == "__main__":
    main()