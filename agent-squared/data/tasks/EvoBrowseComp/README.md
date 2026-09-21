---
license: cc-by-nc-sa-4.0
task_categories:
- question-answering
language:
- en
- zh
---

# EvoBrowseComp: Benchmarking Search Agents on Evolving Knowledge

**EvoBrowseComp** is an evolving benchmark consisting of 400 English and 400 Chinese contamination-free complex questions synthesized via live-web traversal. This dataset is introduced in the paper: [EvoBrowseComp: Benchmarking Search Agents on Evolving Knowledge](https://huggingface.co/papers/2606.13120).

The benchmark addresses the limitations of static knowledge benchmarks by providing questions synthesized from fresh, live-web data to prevent test-set contamination and parametric memorization in Large Language Models.

### Data Access

All QA samples are encrypted, and one can decrypt the data via the following scripts:

```bash
python3 -u data_decrypt.py --input EvoBrowComp-EN-encrypted.jsonl --output EvoBrowComp-EN-decrypted.jsonl
```

```bash
python3 -u data_decrypt.py --input EvoBrowComp-ZH-encrypted.jsonl --output EvoBrowComp-ZH-decrypted.jsonl
```

### Disclaimer

This dataset is intended solely for research purposes. All statements contained within were automatically collected from publicly available sources on the Internet via web-based tools. The views expressed do not represent those of the author or any affiliated institution.