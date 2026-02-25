import numpy as np
from typing import List, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from utils.llm_provider import LLMFactory

class TopicDriftDetector:
    """
    Detects if the current user input significantly deviates from the session history
    using weighted embeddings.
    """
    def __init__(self, threshold: float = 0.65, decay_factor: float = 0.8):
        self.threshold = threshold
        self.decay_factor = decay_factor
        try:
            self.embedder = LLMFactory.get_embeddings()
        except Exception:
            # Fallback or disabled if OpenAI key is missing
            self.embedder = None

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        a = np.array(a)
        b = np.array(b)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    async def check_drift(self, history: List[BaseMessage], new_input: str) -> dict:
        """
        Returns a dict with drift details.
        """
        default_result = {"drift": False, "similarity": 1.0, "current_topic": "Unknown", "new_topic": new_input}
        if not self.embedder or not history or not new_input:
            return default_result

        # 1. Get embedding for new input
        try:
            new_emb = self.embedder.embed_query(new_input)
        except Exception:
            return default_result

        # 2. Get embeddings for history (Human messages only for topic context)
        human_msgs = [m.content for m in history if isinstance(m, HumanMessage) and m.content]
        if not human_msgs:
            return default_result

        try:
            history_embs = self.embedder.embed_documents(human_msgs)
        except Exception:
            return default_result

        # 3. Calculate weighted average embedding of history
        weighted_sum = np.zeros_like(new_emb)
        total_weight = 0.0
        
        for i, emb in enumerate(reversed(history_embs)):
            weight = self.decay_factor ** i
            weighted_sum += np.array(emb) * weight
            total_weight += weight
            
        if total_weight == 0:
            return default_result
            
        avg_history_emb = weighted_sum / total_weight

        # 4. Compare
        similarity = self._cosine_similarity(new_emb, avg_history_emb.tolist())
        
        # 5. Extract "topic" (last few messages for current context)
        current_topic = human_msgs[-1] if human_msgs else "Unknown"
        
        return {
            "drift": similarity < self.threshold,
            "similarity": float(similarity),
            "current_topic": current_topic,
            "new_topic": new_input
        }
