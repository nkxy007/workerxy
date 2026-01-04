from typing_extensions import TypedDict
import operator
#from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage, ChatMessage
from langchain_core.tools import tool
import creds
import os
from pydantic import BaseModel, Field
#from langgraph.prebuilt import ToolNode, create_react_agent, InjectedState
from langgraph.graph import START, END, StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import BaseTool
import traceback
from time import sleep
from deepagents import create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
from langchain.agents import create_agent
from prompts import network_activity_planner_agent_template, LAN_subagent_template

# Evaluation with Trulens imports
from trulens.core import Feedback, TruSession, Select
from trulens.core.feedback.selector import Selector
from trulens.providers.openai import OpenAI as TrulensOpenAI
from trulens.apps.langgraph import TruGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents.middleware import PIIMiddleware
from custom_middleware.netpii_middlewares import PIIPseudonymizationMiddleware


## models keys
os.environ["OPENAI_API_KEY"] = creds.OPENAI_KEY
os.environ["ANTHROPIC_API_KEY"] = creds.ANTHROPIC_KEY



# models
thinking_model_mini = ChatOpenAI(model="gpt-5-mini", api_key=creds.OPENAI_KEY)
thinking_model = ChatOpenAI(model="gpt-5.1", api_key=creds.OPENAI_KEY)
thinking_model_response = ChatOpenAI(model="gpt-5", api_key=creds.OPENAI_KEY, use_responses_api=True)
action_minimal_thinking_model = ChatOpenAI(model="gpt-5-mini", api_key=creds.OPENAI_KEY, reasoning={"effort": "minimal"})
multi_purpose_model = ChatOpenAI(model="gpt-4.1", api_key=creds.OPENAI_KEY)
coding_model = ChatOpenAI(model="gpt-5.1-codex", api_key=creds.OPENAI_KEY)
bias_removal_model = ChatAnthropic(model="claude-4", api_key=creds.ANTHROPIC_KEY)
googla_light_model = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", api_key=creds.GEMINI_KEY)
googla_heavy_model = ChatGoogleGenerativeAI(model="gemini-3-pro", api_key=creds.GEMINI_KEY)


# local tools
@tool
def search_internet(query: str) -> str:
    """Search the internet for a given query and return summarized results.
    This tool is used if the model doesnt have a confidence over 75% on the immediate response to the query.
    Args:
        query (str): The search query.
    Returns:
        str: search results.
    """
    # Simulate an internet search
    print("="*20)
    print(f"Searching the internet for: {query}")
    response = thinking_model.invoke(
        [HumanMessage(content=f"Search the internet for: {query}")], 
        tools=[{"type":"web_search"}])
    return f"Search results for '{query}' are: {response.content}"

@tool
def user_clarification_and_action_tool(question: str, intention:str="") -> str:
    """Ask the user for clarification on a given question or for user to take action.
    This tool is used if the model needs more information from the user to provide an accurate response.
    This tool can also be used by the AI model to ask user to take action and report when the action is 
    completed such actions can be like ping from user laptop, get info from user`s machine. or any other action to be taken by a remote user.
    Args:
        question (str): The question or action to ask the user. it can be a multi part question.
        intention (str): The intention behind the question or action (optional).
    Returns:
        str: user's clarification.
    """
    # Simulate asking the user for clarification
    print(f"Agent needs more information to answer: {question} - intention: {intention}")
    response = input(f"Agent needs more information to continue:\n {question}\nPlease provide clarification: ")
    return f"User clarification for '{question}': {response=}"

@tool
def skill_generator_from_documentation(documentation: str) -> str:
    """Generate a list of skills from the provided documentation.
    This tool is used to extract relevant skills that can be used by the agent.
    Args:
        documentation (str): The documentation text.
    Returns:
        str: A list of skills extracted from the documentation.
    """
    #TODO: extract the know how from the documentation and generate skill and save skill under skills directory
    # in appropriate directory and SKILL.md file
    # this tool learns the knowledge from the documentation and create a trajectory or a memory of what is in the document
    # how to use that knowledge to solve problems. if it is an application documentation it can learne steps of how to use the application
    # for instance configure ip address: menu > settings > network settings > configure IP address, etc.
    # this is a placeholder implementation
    print(f"Generating skills from documentation.")



async def main():

    ## MCP client and tools
    client = MultiServerMCPClient(
        {
            "network": {
                # Make sure you start your weather server on port 8000
                "url": "http://localhost:8000/mcp",
                "transport": "streamable_http",
            }
        }
    )
    tools = await client.get_tools()
    design_tools = [tool for tool in tools if tool.name in ["read_network_diagram", "read_design_document"]]
    cloud_tools = [tool for tool in tools if tool.name in ["aws_tool", "azure_tool", "gcp_tool", "ssh_tool"]]



    ## Create Subagents 
    knowledge_acquisition_subagent = {
        "name": "knowledge_acquisition_subagent",
        "description": "Agent specialized in acquiring sdditional knowledge from various sources such as internet, search and documentation, detailed design, diagrams, etc. The acquired knowledge can be on topology details, network additional knowledge, devices specific details. This knowledge acquisition is necessary where the model confidence is low on the information provided by the user or if more clarification is needed from the user.",
        "system_prompt": "You are a knowledge acquisition expert agent. You help acquiring knowledge from various sources such as detailed design if present, network diagrams, internet, search and documentation, etc. You get invoked only if there is a need to enhance the information given by the user or if clarification to what the user is asking can be acquired from the documents or from the user, in some cases where you have no knowledge you can run a tool to ask user for clarification. your goal is to acquire more knowledge and share with the main agent to help the main agent accomplish its task.",
        "tools": [search_internet, user_clarification_and_action_tool],
        "model": action_minimal_thinking_model,
        }
    
    LAN_subagent = {
        "name": "LAN_subagent",
        "description": "Agent specialized in the LAN network activities such as routing and switching related tasks.",
        "system_prompt": LAN_subagent_template,
        "tools": tools + [search_internet, user_clarification_and_action_tool],
        "model": action_minimal_thinking_model,  # Optional override, defaults to main agent model
        }

    network_design_subagent = {
        "name": "network_design_subagent",
        "description": "Agent specialized in network design and architecture tasks such as reading networkd diagram and reading design documents.",
        "system_prompt": "You are a network design expert. You help analyzing design and architect of networks in diagrams and documents.",
        "tools": design_tools,
        "model": multi_purpose_model,
    }

    cloud_computing_subagent = {
        "name": "cloud_computing_subagent",
        "description": "Agent specialized in cloud computing related tasks such as AWS, Azure, GCP,  etc.",
        "system_prompt": "You are a cloud computing expert agent. You help with cloud computing related tasks.",
        "tools": cloud_tools + [search_internet],
        "model": action_minimal_thinking_model,
    }

    subagents = [LAN_subagent, knowledge_acquisition_subagent, network_design_subagent, cloud_computing_subagent]
    ## create deep agent
    # TODO: add PII middleware to mask sensitive info like IPs, MACs, etc.
    # TODO: add way to load skills from skill.md and add it to the different system_prompt, check if the
    # langgraph dynamic prompt with function works with deepangents
    # or for skills we can ise f-string to the system_prompt and have a filed <skillS> </skills> that is filled with skills
    # skills will be defined before the net_deep_agent is defined.
    net_deep_agent =  create_deep_agent(
        tools=tools,
        system_prompt=network_activity_planner_agent_template,
        subagents=subagents,
        model=thinking_model_mini,
        )
    question_1 = """There is a connectivity issue in the LAN network and user with IP 10.10.10.4 and mac address aaaa.bb12.3456"
    is unable to reach any application, check why. it is connected on switch with management IP address of 192.168.81.222"""
    
    question_1_1 = """There is a connectivity issue in Brisbane LAN network and user with IP 10.10.10.4 and mac address 00:50:79:66:68:07"
    is unable to reach any application, check why. it is connected on switch, switch model is huaweis5530"""
    question_2 = """There is a connectivity issue in Brisbane LAN network and user with IP 10.10.10.4 and mac address 00:50:79:66:68:07"
    is unable to reach any application, check why. it is connected on switch"""

    question_3 = """There is a connectivity issue  incident reported by Nirali Patel work on it"""

    async for chunk in net_deep_agent.astream({"messages": question_2}):
        print("New chunk received:.......................................................\n")
        print(f"{chunk=}")
        if "messages" in chunk.get("model",""):
            print("==="*10)
            chunk["model"]["messages"][-1].pretty_print()
        elif "messages" in chunk.get("tools",""):
            print("+++"*10)
            chunk["tools"]["messages"][-1].pretty_print()

    # evaluation layer 

    session = TruSession()
    session.reset_database()
    # Goal-Plan-Act evaluation provider
    gpa_eval_provider = TrulensOpenAI(model_engine="gpt-4.1",
                                      api_key=creds.OPENAI_KEY)
    
    # Goal-Plan-Act: Logical consistency of trace
    f_logical_consistency = Feedback(
        gpa_eval_provider.logical_consistency_with_cot_reasons,
        name="Logical Consistency",
    ).on({
        "trace": Selector(trace_level=True),
    })
    
    # Goal-Plan-Act: Execution efficiency of trace
    f_execution_efficiency = Feedback(
        gpa_eval_provider.execution_efficiency_with_cot_reasons,
        name="Execution Efficiency",
    ).on({
        "trace": Selector(trace_level=True),
    })
    
    # Goal-Plan-Act: Plan adherence
    f_plan_adherence = Feedback(
        gpa_eval_provider.plan_adherence_with_cot_reasons,
        name="Plan Adherence",
    ).on({
        "trace": Selector(trace_level=True),
    })
    
    # Goal-Plan-Act: Plan quality
    f_plan_quality = Feedback(
        gpa_eval_provider.plan_quality_with_cot_reasons,
        name="Plan Quality",
    ).on({
        "trace": Selector(trace_level=True),
    })
    tru_recorder = TruGraph(net_deep_agent,
                            app_name="coworkerx_agent_app",
                            app_version="0.2",
                            feedbacks=[
                                f_logical_consistency,
                                f_execution_efficiency,
                                f_plan_adherence,
                                f_plan_quality]
    )
    chunks = []
    with tru_recorder as recording:
        async for chunk in net_deep_agent.astream({"messages": [{"role": "user", "content": question_2}]}):
            chunks.append(chunk)
    
    print("\nFinal Response received:.......................................................\n")
    print("--"*40)
    print(f"Final Response: {chunks[-1]}")
    print("--"*40)
    
    from trulens.core import Tru
    import time
    time.sleep(10)  # Wait for feedbacks to complete
    
    # Get the record
    record = recording.get()
    
    # Check if _wait_for_record is async
    if hasattr(record._wait_for_record, '__await__'):
        await record._wait_for_record()
    else:
        record._wait_for_record()
    
    # Fix: Use the correct app_name here!
    records_df, feedback_cols = session.get_records_and_feedback(app_ids=["coworkerx_agent_app"])
    print(f"Records in DB: {len(records_df)}")
    print(f"Feedback columns: {feedback_cols}")
    
    if len(records_df) > 0:
        print(records_df[['input', 'output'] + feedback_cols])
    
    session.run_dashboard()


asyncio.run(main())



