import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

class QueryClassifier:
    def __init__(self, model_path: Path, tokenizer_path: Path, labels_path:Path, max_length: int = 128) -> None:
        self._model_path = Path(model_path)
        self._tokenizer_path = Path(tokenizer_path)
        self._labels_path = Path(labels_path)
        self._max_length = max_length

        
        self._validate_paths()

        self._tokenizer = AutoTokenizer.from_pretrained(self._tokenizer_path)

        self._session = (ort.InferenceSession(str(self._model_path), providers=["CPUExecutionProvider"],))

        with self._labels_path.open( "r", encoding = "utf-8") as file:
            self._labels = json.load(file)

        self._intent_label = (self._labels["intent"])

        self._retrieval_modes = (self._labels["retrieval_mode"])

    def _validate_paths(self)-> None:
        if not self._model_path.exists():
            raise FileNotFoundError(
                f"ONNX model not found: "
                f"{self._model_path}"
            )

        if not self._tokenizer_path.exists():
            raise FileNotFoundError(
                f"Tokenizer not found: "
                f"{self._tokenizer_path}"
            )

        if not self._labels_path.exists():
            raise FileNotFoundError(
                f"Labels file not found: "
                f"{self._labels_path}"
            )

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        logits = (logits - np.max(logits, axis=-1, keepdims=True))

        probabilities = np.exp(logits)

        return (probabilities/probabilities.sum(axis=-1, keepdims = True))

    def predict(self, query:str,) -> dict[str,Any]:
        if not query.strip():
            raise ValueError("Query must not be empty")

        encoding = self._tokenizer(query, truncation=True, max_length=self._max_length, padding="max_length", return_tensors="np")

        outputs = self._session.run(None, {"input_ids": encoding["input_ids"], "attention_mask": encoding["attention_mask"]})

        intent_logits = cast(np.ndarray, outputs[0])

        retrieval_logits = cast(np.ndarray, outputs[1])

        intent_probabilities = self._softmax(intent_logits)[0]
        
        retrieval_probabilities = self._softmax(retrieval_logits)[0]
        
        intent_id = int(np.argmax(intent_probabilities))
        retrieval_mode = int(np.argmax(retrieval_probabilities))
        
        return {
            "intent": self._intent_label[str(intent_id)],
            "intent_confidence": float(np.max(intent_probabilities)),
            "retrieval_mode": self._retrieval_modes[str(retrieval_mode)],
            "retrieval_confidence": float(np.max(retrieval_probabilities))
        }

