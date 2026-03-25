import os
import numpy as np
import logging
from typing import List, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from utils.llm_provider import LLMFactory

logger = logging.getLogger("net_deepagent_cli")

class TopicDriftDetector:
    """
    Detects if the current user input significantly deviates from the session history
    using both weighted embeddings and AI-based relevance to the last assistant response.
    """
    def __init__(self, threshold: float = 0.65, decay_factor: float = 0.8):
        self.threshold = threshold
        self.decay_factor = decay_factor
        
        # Load model name from environment variable
        self.model_name = os.getenv("DRIFT_LLM", "gpt-5-mini")
        
        try:
            self.embedder = LLMFactory.get_embeddings()
            self.llm = LLMFactory.get_llm(self.model_name)
        except Exception as e:
            logger.warning(f"Failed to initialize drift detector components: {e}")
            self.embedder = None
            self.llm = None

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        a = np.array(a)
        b = np.array(b)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    async def _get_ai_relevance(self, last_user_msgs: List[str], last_ai_msg: Optional[str], new_input: str) -> float:
        """Ask LLM to score relevance between 0.0 and 1.0"""
        if not self.llm:
            return 1.0 # Default to relevant if no LLM
            
        context = ""
        if last_user_msgs:
            context += "User's recent messages:\n"
            for i, msg in enumerate(last_user_msgs, 1):
                context += f"{i}. \"{msg}\"\n"
        if last_ai_msg:
            context += f"Assistant previously responded: \"{last_ai_msg}\"\n"
            
        if not context:
            return 1.0

        prompt = (
            f"Previous context:\n{context}\n"
            f"User just asked: \"{new_input}\"\n"
            "On a scale of 0.0 to 1.0, how relevant or related is the user's new question to the previous interaction? "
            "Consider if it's a follow-up, clarification, or directly relates to the context just discussed.\n"
            "Return ONLY a numeric score between 0.0 and 1.0."
        )
        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            # Extract number from response
            import re
            match = re.search(r"([0-9]*\.?[0-9]+)", content)
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))
            return 0.5 # Default if parsing fails
        except Exception as e:
            logger.warning(f"AI relevance scoring failed: {e}")
            return 1.0 # Default to relevant on error to be safe

    async def check_drift(self, history: List[BaseMessage], new_input: str) -> dict:
        """
        Returns a dict with drift details.
        Calculates a hybrid similarity: 50% embedding-based and 50% AI-based.
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

        # 4. Calculate Embedding Similarity
        emb_similarity = self._cosine_similarity(new_emb, avg_history_emb.tolist())
        
        # 5. Calculate AI Relevance (to last interaction if available)
        last_ai_msg = None
        last_user_msgs = []
        
        # Find last AI message
        for m in reversed(history):
            if isinstance(m, AIMessage) and m.content:
                if isinstance(m.content, list):
                    last_ai_msg = "".join([c.get("text", "") for c in m.content if isinstance(c, dict) and c.get("type") == "text"])
                else:
                    last_ai_msg = str(m.content)
                break
        
        # Find up to last 10 Human messages
        for m in reversed(history):
            if isinstance(m, HumanMessage) and m.content:
                last_user_msgs.insert(0, str(m.content))
                if len(last_user_msgs) == 10:
                    break
        
        if last_ai_msg or last_user_msgs:
            ai_similarity = await self._get_ai_relevance(last_user_msgs, last_ai_msg, new_input)
            # Combine 50/50
            final_similarity = (0.3 * emb_similarity) + (0.7 * ai_similarity)
            logger.info(f"Drift Debug: Hybrid Similarity={final_similarity:.2f} (Emb={emb_similarity:.2f}, AI={ai_similarity:.2f})")
        else:
            final_similarity = float(emb_similarity)
            logger.info(f"Drift Debug: Embedding Similarity={final_similarity:.2f} (No context msgs)")
        
        # 5. Extract "topic" (last human message for labeling)
        current_topic = human_msgs[-1] if human_msgs else "Unknown"
        
        return {
            "drift": final_similarity < self.threshold,
            "similarity": float(final_similarity),
            "current_topic": current_topic,
            "new_topic": new_input
        }
