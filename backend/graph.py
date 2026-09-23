import ast
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.output_parsers import PydanticOutputParser
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import SystemMessage,BaseMessage,HumanMessage,ToolMessage
from langgraph.types import interrupt,Command
from langgraph.graph import StateGraph,START,END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing import TypedDict,Annotated, List, Dict, Literal,Optional
# from langgraph.checkpoint.postgres import PostgresSaver
# from psycopg_pool import ConnectionPool

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

from langsmith import traceable
from pydantic import BaseModel
from json_repair import repair_json
import re
from typing import List
from dotenv import load_dotenv
import json
import os
from urllib.parse import quote_plus
load_dotenv()

DB_URL = "postgresql://{}:{}@{}:{}/{}".format(
    os.getenv("DB_USER"),
    quote_plus(os.getenv("DB_PASSWORD", "")),
    os.getenv("DB_HOST", "localhost"),
    os.getenv("DB_PORT", "5432"),
    os.getenv("DB_NAME"),
)



class PptState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    outline: List
    detailed_slides: List[Dict]
    current_slide_index: int
    feedback: str
    topic: str
    research_data: str
    action: Literal[ "continue_slide", "update_outline", "update_slide", "complete", '' ]
    tool_caller: Literal["generate_outline","generate_slide_detail"]
class DetailedPoint(BaseModel):
    key_point: str
    explanation: str
class DetailedSlideOutput(BaseModel):
    slide_number: int
    slide_title: str
    layout: Literal[
        "bullets",
        "bullets_with_text",
        "paragraph",
        "two_column",
        "mixed"
    ]
    intro_line: Optional[str] = None
    bullet_points: Optional[List[str]] = None
    supporting_text: Optional[str] = None
    paragraphs: Optional[List[str]] = None

model = ChatGroq(model="openai/gpt-oss-120b")
# model = ChatAI21(model="jamba-mini-2-2026-01")
searchTool = TavilySearchResults(max_results=2)
tools = [searchTool]
model_with_tools = model.bind_tools(tools)
detailed_parser = PydanticOutputParser(pydantic_object= DetailedSlideOutput)

OUTLINE_SYSTEM_PROMPT = SystemMessage(
    content=f"""You are an expert presentation designer.

Your task:
Generate ONLY the presentation slide titles.

Example:
["Title 1", "Title 2", "Title 3"]
    
Strict Rules:
- Generate EXACTLY the number of slides requested by the user.
- Ensure logical flow from introduction to conclusion.
- Keep slide titles concise but descriptive.
- Use tools only if factual accuracy is required.
- Return a Python list of strings.
- No explanations.
""")
DETAIL_SYSTEM_PROMPT = SystemMessage(content=f"""
You are a professional presentation designer.

Your job is to generate visually balanced slide content for a PowerPoint presentation.

For each slide choose the most appropriate layout or a mix of layouts  and generate structured content.

Available layouts:
- bullets
- bullets_with_text
- paragraph
- mixed


{detailed_parser.get_format_instructions()}


Rules:
- Slides should be informative but not crowded.
- Include at least 1 statistic with source
- Use clear, short content (120-150 words)
- Bullet points: 5–7 items, short phrases
- Keep slide visually balanced
Return JSON only.
""")


@traceable(name="Generate Outline")
def generate_outline_node(state: PptState):
    """Step 1: Generate presentation outline"""
    messages = state["messages"] + [OUTLINE_SYSTEM_PROMPT]

    result = model_with_tools.invoke(messages)
    usage = result.response_metadata.get("token_usage", {})

    output = {
        'messages':[result],
        'current_slide_index':0,
        "tool_caller": "generate_outline",
        "usage": usage
            } 
    if result.content:
        try:
            # print('result.content',result.content)
            output['outline'] = json.loads(result.content)
            
        except json.JSONDecodeError as e:
            print('generate_outline_node',e)
    return output

@traceable(name="Generate Slide Detail")
def generate_slide_detail_node(state: PptState):
    """Generate detailed content using research data"""
    # print('state',state['messages'])
    outline = state['outline']
    current_index = state['current_slide_index']
    detailed_slides = state.get('detailed_slides', [])
    total_slides = len(outline)
    current_slide = outline[current_index]
    
    
    if current_index >= total_slides:
        return {"action": "complete"}
    research = state.get('research_data', {})
    output = {
        "tool_caller": "generate_slide_detail",
        "current_slide_index": current_index
    }
    
    

    
    if state['action'] == "update_slide":
        feedback = state['feedback']
        last_slide = detailed_slides.pop()
        prompt = HumanMessage(content=f"""
Update this slide with research data:
Research: {research}
Current Content: {last_slide}
Feedback: {feedback}
        """)
        messages = [DETAIL_SYSTEM_PROMPT, prompt]  
        output['messages'] = messages



    else:

        prompt = HumanMessage(content=f"""
Slide: {current_slide}
Topic: {state['topic']}

If this slide needs current statistics, market data, or recent research, use the search tool first and get data till current {datetime.now().year} year.
For conceptual, instructional, or introductory slides, generate content directly without searching.
""")
        messages = [DETAIL_SYSTEM_PROMPT, prompt]
        output['messages'] = messages


        last_message = state["messages"][-1] if state["messages"] else None
        # print('last_message',last_message)
        resuming_from_tool = (
            last_message is not None and 
            last_message.type == "tool"  # ToolMessage means search just completed
        )

        # print('resuming_from_tool',resuming_from_tool)

        if resuming_from_tool:
            # Pass full history so model sees its own search results and can now generate
            messages = messages + state["messages"][-2:] 
        # print('messages',messages)
        
    # print("\n\n\n\nmessages",messages)

    result = model_with_tools.invoke(messages)
    # print("\n\n\n\nresult",result)

    # usage = result.response_metadata.get("token_usage", {})
    # output["usage"] = usage
    
    if result.content:
        try:
            new_slide = detailed_parser.parse(repair_json(str(result.content))).model_dump()
            detailed_slides.append(new_slide)
            output['detailed_slides'] = detailed_slides
            output['current_slide_index'] = current_index + 1
            
        except Exception as e:
            print('error',e)
    
    if output['current_slide_index'] == total_slides:
        output["action"] = "complete"
    # output["action"] = "complete"
    # print("output['messages']",output['messages'])
    output['messages'].append(result)
    # print('after append',output['messages'])
    return output



def route_after_tools(state: PptState):
    return state["tool_caller"]

def human_decision(state: PptState):
    decision = interrupt({})
    if decision['action'] == "update_outline":

        return {
            'action': "update_outline",
            "messages":[decision['feedback']]
            }
    elif decision['action'] == 'continue_slide':
        return {'action':'continue_slide'}
    elif decision['action'] == 'update_slide':
        return {'action':'update_slide'}
def route_after_human(state: PptState):
    action = state['action']
    if action == 'update_outline':
        return "generate_outline"
    elif action in ('continue_slide', 'update_slide'):
        return "generate_slide_detail"
    elif action == 'complete':  
        return END
    return END

def tools_condition(state: PptState):
    """Route to tools if last message has tool calls"""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "__end__"

def build_workflow():
    workflow = StateGraph(PptState)
    workflow.add_node("generate_outline", generate_outline_node)
    # workflow.add_node("research_slide", research_slide_node)
    workflow.add_node("generate_slide_detail", generate_slide_detail_node)
    workflow.add_node("human_decision", human_decision)
    workflow.add_node("tools", ToolNode(tools))
    
    workflow.add_edge(START, "generate_outline")

    workflow.add_conditional_edges( #done
        "generate_outline",
        tools_condition,
        {
            "tools": "tools",
            "__end__": "human_decision",
        },
    )

    workflow.add_conditional_edges(
        "human_decision",
        route_after_human,
        {
            "generate_outline": "generate_outline",
            "generate_slide_detail": "generate_slide_detail",
            END: END,
        },
    )
    
    

    workflow.add_conditional_edges(
        "generate_slide_detail",
        tools_condition,
        {
            "tools": "tools",
            "__end__": "human_decision",
        },
    )
    workflow.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "generate_outline": "generate_outline",
            "generate_slide_detail": "generate_slide_detail",
        },
    )

    return workflow

# def create_checkpointer_and_graph(db_url: str):
#     if not db_url:
#         raise ValueError('Database Url environment variable not set')
#     connection_kwargs = {
#             "autocommit": True,
#             "prepare_threshold": 0,
#         }
#     pool = ConnectionPool(
#         conninfo=db_url,
#             max_size=20,
#             kwargs=connection_kwargs,
#     )
#     checkpointer = PostgresSaver(pool)
#     checkpointer.setup()
#     workflow = build_workflow()
#     graph = workflow.compile(checkpointer=checkpointer)
#     return checkpointer, graph


def create_checkpoint_and_graph():
    conn = sqlite3.connect(
        "checkpoints.db",
        check_same_thread=False
    )

    checkpointer = SqliteSaver(conn)

    workflow = build_workflow()
    graph = workflow.compile(
        checkpointer=checkpointer
    )

    return checkpointer, graph