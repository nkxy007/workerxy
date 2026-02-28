import re
import logging
from typing import Any, Callable, Iterable, List, Optional, Sequence, Union, cast, Awaitable
from copy import deepcopy

from langchain_core.messages import AnyMessage, BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain.agents.middleware import (
    AgentMiddleware, 
    SummarizationMiddleware, 
    AgentState, 
    ModelRequest, 
    ModelResponse,
    ClearToolUsesEdit,
    ContextEditingMiddleware
)
from langchain.agents.middleware.context_editing import ContextEdit
from langchain.chat_models import init_chat_model

logger = logging.getLogger(__name__)

class PruneSkillsEdit(ContextEdit):
    """Context edit strategy to prune old messages containing skill information."""
    
    def __init__(
        self, 
        trigger_tokens: int, 
        keep_recent: int = 1, 
        skill_pattern: str = r"\[SKILL INFO\]|<skill>|Loaded skill:"
    ):
        """
        Initialize PruneSkillsEdit.
        
        Args:
            trigger_tokens: Token count threshold to trigger pruning.
            keep_recent: Number of most recent skill messages to keep.
            skill_pattern: Regex pattern to identify skill-related messages.
        """
        self.trigger_tokens = trigger_tokens
        self.keep_recent = keep_recent
        self.skill_pattern = re.compile(skill_pattern, re.IGNORECASE)

    def apply(self, messages: List[AnyMessage], count_tokens: Callable[[Sequence[BaseMessage]], int]) -> None:
        """Apply the pruning logic to the messages list."""
        current_tokens = count_tokens(messages)
        if current_tokens <= self.trigger_tokens:
            return

        # Find indices of messages containing skill info
        skill_indices = []
        for i, msg in enumerate(messages):
            content = str(msg.content)
            if self.skill_pattern.search(content):
                skill_indices.append(i)

        if len(skill_indices) <= self.keep_recent:
            return

        # Indices to remove (all but the most recent `keep_recent`)
        to_remove = skill_indices[:-self.keep_recent]
        
        logger.info(f"Pruning {len(to_remove)} old skill messages. Context tokens: {current_tokens}")
        
        # Remove in reverse order to preserve indices
        for i in reversed(to_remove):
            messages.pop(i)

class AdvancedContextMiddleware(AgentMiddleware):
    """
    Advanced context management middleware that combines skill pruning, 
    tool output removal, and summarization.
    
    This middleware monitors the conversation context size and triggers pruning
    and summarization when the token count reaches a configurable threshold 
    (defaulting to 85% of the model's maximum context capacity).

    Usage:
    ------
    To attach this middleware to an agent, pass it in the `middleware` list during
    agent initialization:

    ```python
    from custom_middleware.skill_pruning_middleware import AdvancedContextMiddleware
    
    # 1. Define your primary model's max context limit (e.g., 200,000)
    # 2. Add AdvancedContextMiddleware to the agent's middleware stack
    agent = create_agent(
        model=primary_model,
        tools=your_tools,
        middleware=[
            AdvancedContextMiddleware(
                max_tokens=200000,   # Required: Max context of your primary model
                trigger_ratio=0.85,  # Optional: Trigger at 85% capacity
                keep_skills=1,       # Optional: Keep 1 most recent skill info msg
                keep_tool_uses=3     # Optional: Keep 3 most recent tool results
            )
        ]
    )
    ```

    Inputs:
    -------
    - max_tokens (int): The absolute token limit of your primary LLM.
    - trigger_ratio (float): The percentage (0.0 to 1.0) of max_tokens that 
      triggers context cleaning. Default is 0.85.
    - keep_skills (int): Number of most recent skill-loading messages to persist. 
      Older ones are pruned first. Default is 1.
    - keep_tool_uses (int): Number of most recent tool results to keep in context. 
      Older tool outputs are cleared after pruning skills. Default is 3.
    - summarize_model (BaseChatModel | str, optional): The model used to generate 
      summaries of pruned conversation history. Defaults to "gpt-5-mini".
    - token_count_method (str): Method to count tokens ("approximate" or "model"). 
      Default is "approximate".
    """
    
    def __init__(
        self, 
        max_tokens: int, 
        trigger_ratio: float = 0.85,
        keep_skills: int = 1,
        keep_tool_uses: int = 3,
        summarize_model: Optional[Union[Any, str]] = "gpt-5-mini",
        token_count_method: str = "approximate"
    ):
        """
        Initialize the AdvancedContextMiddleware.
        
        Args:
            max_tokens: The maximum context window of the model.
            trigger_ratio: The ratio of max_tokens at which to trigger context editing (0-1).
            keep_skills: Number of recent skill messages to preserve.
            keep_tool_uses: Number of recent tool uses to preserve.
            summarize_model: Model instance or string name to use for summarization. 
                             Defaults to "gpt-5-mini".
            token_count_method: Method to count tokens ("approximate" or "model").
        """
        super().__init__()
        self.max_tokens = max_tokens
        self.trigger_tokens = int(max_tokens * trigger_ratio)
        self.token_count_method = token_count_method
        
        # Internal middlewares we compose
        self.context_editor = ContextEditingMiddleware(
            edits=[
                PruneSkillsEdit(trigger_tokens=self.trigger_tokens, keep_recent=keep_skills),
                ClearToolUsesEdit(trigger=self.trigger_tokens, keep=keep_tool_uses)
            ],
            token_count_method=token_count_method
        )
        
        # Resolve summarization model
        if isinstance(summarize_model, str):
            try:
                summarize_model = init_chat_model(summarize_model)
            except Exception as e:
                logger.warning(f"Failed to initialize summarize_model '{summarize_model}': {e}. Summarization disabled.")
                summarize_model = None

        self.summarizer = None
        if summarize_model:
            # Summarize when we hit the trigger, keep 20 most recent messages as context
            self.summarizer = SummarizationMiddleware(
                model=summarize_model,
                trigger=("tokens", self.trigger_tokens),
                keep=("messages", 20) 
            )

    def wrap_model_call(self, request, handler):
        """Synchronous model call wrapper."""
        initial_msg_count = len(request.messages)
        
        def context_edited_handler(req):
            # Log if pruning happened in ContextEditingMiddleware step
            current_count = len(req.messages)
            if current_count < initial_msg_count:
                logger.info(f"Context pruning active: removed {initial_msg_count - current_count} old messages.")
            
            if self.summarizer:
                # SummarizationMiddleware implements before_model, not wrap_model_call
                state = {"messages": req.messages}
                updates = self.summarizer.before_model(state, req.runtime)
                if updates and "messages" in updates:
                    logger.info("Context summarization active: condensing older conversation history.")
                    req = req.override(messages=updates["messages"])
            return handler(req)
            
        return self.context_editor.wrap_model_call(request, context_edited_handler)

    async def awrap_model_call(self, request, handler):
        """Asynchronous model call wrapper."""
        initial_msg_count = len(request.messages)
        
        async def context_edited_handler(req):
            # Log if pruning happened in ContextEditingMiddleware step
            current_count = len(req.messages)
            if current_count < initial_msg_count:
                logger.info(f"Context pruning active: removed {initial_msg_count - current_count} old messages.")
            
            if self.summarizer:
                # SummarizationMiddleware implements abefore_model, not awrap_model_call
                state = {"messages": req.messages}
                updates = await self.summarizer.abefore_model(state, req.runtime)
                if updates and "messages" in updates:
                    logger.info("Context summarization active: condensing older conversation history.")
                    req = req.override(messages=updates["messages"])
            return await handler(req)
            
        return await self.context_editor.awrap_model_call(request, context_edited_handler)
