import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from pathlib import Path
from net_deepagent_cli.association import InteractionAssociationEngine
from net_deepagent_cli.loop import interactive_loop
from net_deepagent_cli.ui import TerminalUI
from langchain_core.messages import HumanMessage, AIMessage

class TestAssociationIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_agent = MagicMock()
        self.mock_ui = MagicMock(spec=TerminalUI)
        self.mock_ui.agent_name = "test_agent"
        # Mock console behavior
        self.mock_ui.console = MagicMock()
        self.args = MagicMock()
        self.args.automatic_context_detection = True
        self.args.association_window = 5

    @patch('net_deepagent_cli.loop.AutomataManager')
    @patch('net_deepagent_cli.association.Embedder')
    @patch('net_deepagent_cli.loop.handle_command', new_callable=AsyncMock)
    @patch('net_deepagent_cli.loop.stream_agent_response', new_callable=AsyncMock)
    async def test_association_triggers_resume_prompt(self, mock_stream, mock_handle_cmd, MockEmbedder, MockAutomata):
        # 1. Setup mocks
        mock_embedder = MockEmbedder.return_value
        mock_embedder.embed_query = MagicMock(side_effect=lambda x: [0.1] * 1536)
        
        # Mock LLM and bind_tools
        mock_llm = MagicMock()
        mock_bound_llm = AsyncMock()
        mock_llm.bind_tools.return_value = mock_bound_llm
        
        # Mock researcher agent response (skip tool call for simplicity in this first test)
        mock_bound_llm.ainvoke.return_value = MagicMock(
            content='{"is_past_reference": true, "context_summary": "bgp routing", "time_hint": "yesterday"}',
            tool_calls=[]
        )
        self.mock_agent.llm = mock_llm
        
        with patch('net_deepagent_cli.association.Path.home', return_value=Path('/tmp')):
            with patch('net_deepagent_cli.association.Path.exists', return_value=True):
                mock_session = MagicMock(spec=Path)
                mock_session.stem = "old_session"
                mock_session.suffix = ".json"
                mock_session.stat.return_value.st_mtime = 1736419200
                mock_session.open = mock_open(read_data='[{"type": "human", "content": "help with bgp"}]')
                
                with patch('net_deepagent_cli.association.Path.glob', return_value=[mock_session]):
                    with patch('net_deepagent_cli.association.datetime') as mock_datetime:
                            import datetime
                            mock_datetime.datetime.now.return_value = datetime.datetime(2025, 1, 10, 12, 0)
                            mock_datetime.datetime.fromtimestamp.return_value = datetime.datetime(2025, 1, 9, 12, 0)
                            mock_datetime.timedelta = datetime.timedelta
                            
                            self.mock_ui.get_user_input = AsyncMock(side_effect=["remember that bgp stuff?", "exit"])
                            self.mock_ui.prompt_resume_session.return_value = True
                            
                            try:
                                await interactive_loop(self.mock_agent, self.args, self.mock_ui)
                            except (EOFError, StopAsyncIteration):
                                pass

        # 3. Assertions
        self.mock_ui.prompt_resume_session.assert_called_with("old_session", "1 days ago")
        mock_handle_cmd.assert_any_call("/session resume old_session", self.mock_ui, unittest.mock.ANY, agent=self.mock_agent)

    @patch('net_deepagent_cli.loop.AutomataManager')
    @patch('net_deepagent_cli.association.Embedder')
    @patch('net_deepagent_cli.loop.handle_command', new_callable=AsyncMock)
    @patch('net_deepagent_cli.loop.stream_agent_response', new_callable=AsyncMock)
    async def test_association_waits_for_clarification(self, mock_stream, mock_handle_cmd, MockEmbedder, MockAutomata):
        # 1. Setup mocks
        mock_embedder = MockEmbedder.return_value
        mock_embedder.embed_query = MagicMock(side_effect=lambda x: [0.1] * 1536)
        
        mock_llm = MagicMock()
        mock_bound_llm = AsyncMock()
        mock_llm.bind_tools.return_value = mock_bound_llm
        
        # First call: Weak match info
        mock_bound_llm.ainvoke.side_effect = [
            MagicMock(content='{"is_past_reference": true, "context_summary": "vague thing", "match": null}', tool_calls=[]),
            # Second call (after clarification): Strong match
            MagicMock(content='{"is_past_reference": true, "context_summary": "bgp routing", "match": null}', tool_calls=[])
        ]
        self.mock_agent.llm = mock_llm
        
        with patch('net_deepagent_cli.association.Path.home', return_value=Path('/tmp')):
            with patch('net_deepagent_cli.association.Path.exists', return_value=True):
                mock_session = MagicMock(spec=Path)
                mock_session.stem = "strong_match_after_clarification"
                mock_session.suffix = ".json"
                mock_session.stat.return_value.st_mtime = 1736419200
                mock_session.open = mock_open(read_data='[{"type": "human", "content": "bgp stuff"}]')
                
                with patch('net_deepagent_cli.association.Path.glob', return_value=[mock_session]):
                    # Mock _cosine_similarity to return 0.5 then 0.9
                    with patch('net_deepagent_cli.association.InteractionAssociationEngine._cosine_similarity', side_effect=[0.5, 0.9]):
                        with patch('net_deepagent_cli.association.datetime') as mock_datetime:
                            import datetime
                            mock_datetime.datetime.now.return_value = datetime.datetime(2025, 1, 10, 12, 0)
                            mock_datetime.datetime.fromtimestamp.return_value = datetime.datetime(2025, 1, 9, 12, 0)
                            mock_datetime.timedelta = datetime.timedelta
                            
                            # Trigger input -> Clarification input -> Exit
                            self.mock_ui.get_user_input = AsyncMock(side_effect=["remember stuff?", "bgp specifics", "exit"])
                            self.mock_ui.prompt_resume_session.return_value = True
                            
                            try:
                                await interactive_loop(self.mock_agent, self.args, self.mock_ui)
                            except (EOFError, StopAsyncIteration):
                                pass

        # 3. Assertions
        # Check if UI print_message was called with the clarification prompt
        self.mock_ui.print_message.assert_any_call(
            unittest.mock.ANY,
            role="assistant"
        )
        # Check if we eventually tried to resume the correct session
        mock_handle_cmd.assert_any_call("/session resume strong_match_after_clarification", self.mock_ui, unittest.mock.ANY, agent=self.mock_agent)

if __name__ == '__main__':
    unittest.main()
