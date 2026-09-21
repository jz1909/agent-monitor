import base64
import json
import argparse

def decrypt(ciphertext_b64: str, key_b64: str) -> str:
    key = base64.b64decode(key_b64)
    encrypted = base64.b64decode(ciphertext_b64)
    decrypted = bytes([a ^ b for a, b in zip(encrypted, key)])
    return decrypted.decode('utf-8')


def decrypt_file(input_file_dir: str, output_file_dir: str):
    with open(input_file_dir, "r", encoding="utf-8") as f:
        data = f.readlines()
    for idx,d in enumerate(data):
        data[idx] = json.loads(d)
    
    results = []
    for item in data:
        results.append({
            "question": decrypt(item["question"], item["question_key"]),
            "answer": decrypt(item["answer"], item["answer_key"])
        })
        
    with open(output_file_dir, "w", encoding="utf-8") as f:
        for item in results:
            json.dump(item,f,ensure_ascii=False)
            f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Decrypt EvoBrowseComp encrypted file.")
    parser.add_argument("--input", required=True, help="Path to the encrypted file")
    parser.add_argument("--output", required=True, help="Path to save the decrypted file")
    args = parser.parse_args()

    decrypt_file(args.input, args.output)

if __name__ == "__main__":
    main()
