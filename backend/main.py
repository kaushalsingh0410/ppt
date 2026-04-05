import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from uuid import uuid4
from datetime import datetime
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from dotenv import load_dotenv
from groq import RateLimitError
import os
import re
import time
from .database import get_db
from .models import Thread
from .graph import create_ckeckpointer_and_graph
from .ppt_generator import PPTGenerator
from .schemas import Ppt, ThreadResponse, ThreadWithStateResponse
from fastapi.responses import StreamingResponse
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from urllib.parse import quote_plus

load_dotenv()

BASE_DIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(BASE_DIT,"media")
os.makedirs(MEDIA_DIR,exist_ok=True)
# PPT_URL = os.getenv('PPT_URL')
PPT_URL = "postgresql://{}:{}@{}:{}/{}".format(
    os.getenv("DB_USER"),
    quote_plus(os.getenv("DB_PASSWORD", "")),
    os.getenv("DB_HOST", "localhost"),
    os.getenv("DB_PORT", "5432"),
    os.getenv("DB_NAME"),
)
app_state = {
    "checkpointer":None,
    "graph":None
}
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app_state["checkpointer"], app_state['graph'] = create_ckeckpointer_and_graph(PPT_URL)
        # scheduler.add_job(my_job, "interval", seconds=14)
        scheduler.add_job(my_job, "interval", minutes=14)
        scheduler.start()
        yield
    finally:
        scheduler.shutdown()
        try:
            if app_state["checkpointer"]:
                pool = app_state["checkpointer"].pool
                if pool:
                    pool.close()
        except Exception as e:
            print(f'Error closing pool: {e}')
def get_graph_deps():
    if not app_state["graph"]:
        raise RuntimeError("Graph not initialized. Check startup logs.")
    if not app_state["checkpointer"]:
        raise RuntimeError("Checkpointer not initialized. Check startup logs.")
    return app_state["checkpointer"], app_state["graph"]

app = FastAPI(lifespan = lifespan)
scheduler = BackgroundScheduler()

def my_job():
    # print("Running scheduled job...")
    response = requests.get('https://ppt-ritey.onrender.com/')
                            # "https://ppt-ritey.onrender.com"
    # print('response',response)

@app.get("/")
def hellow():
    return {"status":'ok'}


@app.post("/states/")
def read_root(ppt: Ppt,db: Session = Depends(get_db), deps: tuple = Depends(get_graph_deps)):
    checkpointer, graph = deps
    config = {'configurable':{'thread_id':ppt.thread_id}}
    try:
        if ppt.topic and ppt.num_slide and ppt.thread_id:
            num_slide = 5 if ppt.num_slide > 5 else ppt.num_slide
            state = {
                "messages": [HumanMessage(content=f"Create a {num_slide}-slide presentation outline on: {ppt.topic}")],
                "topic":ppt.topic,
                "outline": {},
                "detailed_slides": [],
                "current_slide_index": 0,
                "feedback": "",
                "action": "",
                "tool_caller": "generate_outline",
            }
            result =  graph.invoke(state,config = config)['messages'][-1].content
            thread = db.query(Thread).filter(Thread.thread_id == ppt.thread_id).first()
            thread.last_update = '1' 
            db.commit() 
            db.refresh(thread)
            return result
        if ppt.feedback:
            state = Command(resume={
                "action": ppt.action,
                "feedback":ppt.feedback
            })
            result =  graph.invoke(state,config = config)['messages'][-1].content
            return result
        
        if ppt.action == 'continue_slide':
            thread = db.query(Thread).filter(Thread.thread_id == ppt.thread_id).first()
            num_slide = 5 if thread.num_slide > 5 else thread.num_slide
            for i in range(num_slide):        
                state = Command(resume={
                    "action": ppt.action,
                })
                result = graph.invoke(state,config = config)
            return result['messages'][-1].content
    except RateLimitError as e:

        # Extract wait time from error message e.g. "try again in 23m31.776s"

        wait_match = re.search(r'try again in ([^\.]+)', str(e))
        wait_time = wait_match.group(1) if wait_match else "some time"

        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit",
                "message": f"Groq daily token limit reached. Please try again in {wait_time} or for next 24 hours.",
                "wait_time": wait_time
            }
        )

@app.post('/ppt/')
def generate_ppt(ppt: Ppt, deps: tuple = Depends(get_graph_deps),db: Session = Depends(get_db)):
    checkpointer, graph = deps
    try:
        thread = db.query(Thread).filter( Thread.thread_id == ppt.thread_id ).first()
        
        config = {"configurable": {"thread_id":ppt.thread_id}}
        
        state = graph.get_state(config).values
        if not state:
            raise HTTPException(state_code = 404,detail="State not found")

        slides = state.get("detailed_slides",[])
        if not slides:
            raise HTTPException(state_code = 404,detail="No slide data available.")
        title = state["messages"][0].content.split(':')[-1]

        ppt_obj = PPTGenerator(title)
        ppt_obj.generate_from_list(slides)
        ppt_file = ppt_obj.save()
        return StreamingResponse(
                ppt_file,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                headers={
                    "Content-Disposition": f"attachment; filename={title}.pptx"
                }
            )
    except Exception as e:
        print('error',e)
        raise HTTPException(status_code=500,detail=(e))
    

@app.post('/threads/',response_model=ThreadResponse)
def create_threads(ppt: Ppt,db: Session = Depends(get_db)):

    num_slide = 5 if ppt.num_slide > 5 else ppt.num_slide


    thread = Thread(thread_id = str(uuid4()),topic = ppt.topic,num_slide = num_slide,last_update = 'update')
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread

@app.get('/threads/{thread_id}',response_model = ThreadWithStateResponse)
def get_threads(thread_id:str, db: Session = Depends(get_db),deps: tuple = Depends(get_graph_deps)):
    checkpointer, graph = deps
    # print('thread_id',thread_id)
    thread = db.query(Thread).filter(
        Thread.thread_id == thread_id
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail='Thread not found')
    config = {'configurable':{'thread_id':thread_id}}
    state = graph.get_state(config).values
    return {
        "thread": thread,
        "outline": state.get('outline',[]),
        "detailed_slides": state.get('detailed_slides',[]),
    }
@app.get('/threads/',response_model = List[ThreadResponse])
def list_threads(db: Session = Depends(get_db)):
    return db.query(Thread).order_by(desc(Thread.updated_at)).all()

@app.put('/threads/{thread_id}')
def update_threads(thread_id:str, ppt: Ppt, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(
        Thread.thread_id == thread_id
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail='Thread not found')
    thread.topic = ppt.topic 
    db.commit()
    db.refresh(thread)
    return {
        "message":"Thread update successfully",
        "thread": thread
        }
@app.delete('/threads/{thread_id}')
def delete_threads(thread_id:str, db: Session = Depends(get_db),deps: tuple = Depends(get_graph_deps)):
    checkpointer, graph = deps
    thread = db.query(Thread).filter(
        Thread.thread_id == thread_id
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail='Thread not found')
    try:
        checkpointer.delete_thread(thread_id)
    except Exception as e:
        print('delete_threads Exception: ',e)
    db.delete(thread)
    db.commit()
    return {
        "message":"Thread deleted successfully",
        }

@app.get('/sessions/')
def list_sessions(deps: tuple = Depends(get_graph_deps)):
    checkpointer, graph = deps
    checkpointers = list(checkpointer.list(config=None))
    thread_id = list({cp.config["configurable"]['thread_id'] for cp in checkpointers})     
    return thread_id



@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(my_job, "interval", seconds=10)
    scheduler.start()

@app.on_event("shutdown")   
def shutdown_scheduler():
    scheduler.shutdown()