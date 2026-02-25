import os
import json
import logging
import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from utils.llm_provider import LLMFactory
import numpy as np

logger = logging.getLogger("net_deepagent_cli")

class InteractionAssociationEngine:
    def __init__(self, agent_name: str, lookback_days: int = 5, model: str = "gpt-5-mini"):
        self.agent_name = agent_name
        self.lookback_days = lookback_days
        self.model = model
        try:
            self.embedder = LLMFactory.get_embeddings()
        except Exception:
            self.embedder = None
            
        self.session_cache = [] # List of {name, mtime, embedding, summary}
        self.keywords = {"yesterday", "before", "previously", "remember", "last time", "discussed", "project", "fix", "load", "session"}

    def _get_sessions_dir(self) -> Path:
        return Path.home() / ".net-deepagent" / self.agent_name / "sessions"

    async def build_initial_cache(self):
        """Scan sessions and build a fast semantic index of recent topics"""
        if not self.embedder:
            return

        sessions_dir = self._get_sessions_dir()
        logger.info(f"Scanning sessions directory: {sessions_dir}")
        if not sessions_dir.exists():
            logger.warning(f"Sessions directory does not exist: {sessions_dir}")
            return

        now = datetime.datetime.now()
        lookback_limit = now - datetime.timedelta(days=self.lookback_days)
        logger.info(f"Looking back to: {lookback_limit}")

        found_count = 0
        for session_file in sessions_dir.glob("*.json"):
            found_count += 1
            mtime = datetime.datetime.fromtimestamp(session_file.stat().st_mtime)
            if mtime > lookback_limit:
                try:
                    with session_file.open('r') as f:
                        messages = json.load(f)
                    
                    # Extract context from first few human messages
                    human_texts = []
                    for msg in messages:
                        m_type = msg.get('type') or msg.get('role')
                        # Handle nested data structure from LangChain's message_to_dict
                        m_data = msg.get('data', {}) if isinstance(msg.get('data'), dict) else msg
                        
                        if m_type == 'human' or m_type == 'user':
                            content = m_data.get('content', '').strip()
                            if content:
                                human_texts.append(content)
                            if len(human_texts) >= 5: # Slightly more context
                                break
                    
                    if human_texts:
                        summary = "\n".join(human_texts)
                        if summary.strip():
                            embedding = self.embedder.embed_query(summary)
                            self.session_cache.append({
                                "name": session_file.stem,
                                "mtime": mtime,
                                "embedding": embedding,
                                "summary": summary
                            })
                            logger.info(f"Cached session: {session_file.stem}")
                except Exception as e:
                    logger.warning(f"Failed to cache session {session_file}: {e}")
        
        logger.info(f"Total files found: {found_count}, Total cached: {len(self.session_cache)}")

    def _keyword_gate(self, user_input: str) -> bool:
        input_lower = user_input.lower()
        return any(kw in input_lower for kw in self.keywords)

    async def _semantic_gate(self, user_input: str) -> bool:
        if not self.embedder or not self.session_cache:
            return False
            
        if not user_input.strip():
            return False
            
        input_emb = self.embedder.embed_query(user_input.strip())
        for item in self.session_cache:
            sim = self._cosine_similarity(input_emb, item['embedding'])
            if sim > 0.80:
                return True
        return False

    def _cosine_similarity(self, v1, v2):
        a = np.array(v1)
        b = np.array(v2)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    async def detect_reference(self, user_input: str, agent) -> Dict[str, Any]:
        """Use a tool-calling LLM to confirm reference and actively search for a session"""
        
        # 1. Fast Trigger (Optimization)
        if not self._keyword_gate(user_input) and not await self._semantic_gate(user_input):
            return {"is_past_reference": False, "context_summary": None, "time_hint": None, "match": None}

        logger.info(f"Association researcher invoked for: '{user_input}'")

        # 2. Setup Tool
        @tool
        def search_past_interactions(query: str) -> str:
            """
            Search the index of past sessions from the lookback window.
            Returns a list of matching sessions with their scores and summaries.
            """
            # We call our internal search logic
            # Since this tool is sync for simplicity within the agent flow
            logger.info(f"Searching past interactions for query: '{query}'")
            if not self.embedder:
                logger.error("Embedder is missing during search!")
                return "Error: Memory system uninitialized."

            summary_emb = self.embedder.embed_query(query.strip())
            results = []
            now = datetime.datetime.now()
            
            logger.info(f"Cache size: {len(self.session_cache)}")
            for item in self.session_cache:
                sim = self._cosine_similarity(summary_emb, item['embedding'])
                days_ago = (now - item['mtime']).days
                score = sim + (max(0, 5 - days_ago) * 0.01)
                
                logger.info(f"Candidate: {item['name']}, sim={sim:.3f}, score={score:.3f}")
                results.append({
                    "name": item['name'],
                    "score": round(score, 3),
                    "summary": item['summary']
                })
            
            # Sort by score
            results.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"Top result: {results[0]['name'] if results else 'None'}")
            return json.dumps(results[:3], indent=2)

        # 3. Setup Researching Agent
        llm = getattr(agent, 'llm', None)
        if not llm and hasattr(agent, 'base_agent'):
             llm = getattr(agent.base_agent, 'llm', None)
             
        if not llm:
            logger.warning("No LLM found for association researcher. Falling back to LLMFactory.")
            llm = LLMFactory.get_llm(self.model)

        # Use the provided LLM but bind tools
        researcher_llm = llm.bind_tools([search_past_interactions])
        
        messages = [
            SystemMessage(content=(
                f"You are a memory researcher agent for {self.agent_name}. "
                f"Your task is to determine if the user is referring to a past networking project or technical discussion from the last {self.lookback_days} days. "
                "Use the 'search_past_interactions' tool to find relevant technical context IF you suspect a reference. "
                "\nOutput your final analysis purely as a JSON object with this schema:\n"
                "{\n"
                "  \"is_past_reference\": boolean, // True if the user is definitely referring to something past\n"
                "  \"context_summary\": string, // A summary of TECHNICAL FACTS (IPs, subnets, device names) found in the past session to help the main agent answer the current turn. MUST be provided if is_past_reference is true.\n"
                "  \"justification\": string // Why you think it matches or why it doesn't\n"
                "}"
            )),
            HumanMessage(content=user_input)
        ]

        try:
            # Simple 1-step tool loop for speed
            response = await researcher_llm.ainvoke(messages)
            
            if response.tool_calls:
                tool_msg = []
                for tc in response.tool_calls:
                    if tc["name"] == "search_past_interactions":
                        out = search_past_interactions.invoke(tc["args"])
                        tool_msg.append(ToolMessage(content=out, tool_call_id=tc["id"]))
                
                # Get final verdict after tool results
                final_resp = await researcher_llm.ainvoke(messages + [response] + tool_msg)
                content = final_resp.content.strip()
            else:
                content = response.content.strip()
            
            logger.info(f"Researcher raw output: {content}")

            # Clean JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "{" in content:
                 content = content[content.find("{"):content.rfind("}")+1]
            
            verdict = json.loads(content)
            
            # Ensure required keys exist to avoid KeyError in loop.py
            if not isinstance(verdict, dict):
                verdict = {"is_past_reference": False}
            
            if "is_past_reference" not in verdict:
                verdict["is_past_reference"] = False
            
            # Post-process: If we identified a session in the search, find_matching_session again with specifics
            if verdict.get("is_past_reference") and verdict.get("context_summary"):
                 match = await self.find_matching_session(verdict["context_summary"])
                 verdict["match"] = match
            else:
                 verdict["match"] = None
                 
            return verdict
            
        except Exception as e:
            logger.error(f"Error in Researcher detection: {e}")
            return {"is_past_reference": False, "context_summary": None, "match": None}

    async def find_matching_session(self, context_summary: str) -> Optional[Dict[str, Any]]:
        if not self.embedder or not self.session_cache:
            return None
            
        if not context_summary or not context_summary.strip():
            return None
            
        summary_emb = self.embedder.embed_query(context_summary.strip())
        best_match = None
        best_score = -1.0
        
        now = datetime.datetime.now()

        for item in self.session_cache:
            sim = self._cosine_similarity(summary_emb, item['embedding'])
            
            # Recency boost
            days_ago = (now - item['mtime']).days
            score = sim + (max(0, 5 - days_ago) * 0.01)
            
            if score > best_score:
                best_score = score
                best_match = item
        
        if best_match:
            return {
                "name": best_match['name'],
                "score": float(best_score),
                "time_hint": f"{ (now - best_match['mtime']).days } days ago",
                "is_strong_match": bool(best_score > 0.70)
            }
        return None
