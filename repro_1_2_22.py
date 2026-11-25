"""Independent offline single-ToolNode probe; no model calls or external I/O."""
import asyncio, json, threading, time, platform, sys, inspect
from importlib.metadata import version
from pathlib import Path
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

async def run(kind, mode, limit, guarded=False):
    lock=threading.Lock()
    active=peak=0
    n=4
    gate=asyncio.Semaphore(limit)
    def enter():
        nonlocal active,peak
        with lock:
            active+=1
            peak=max(peak,active)
    def leave():
        nonlocal active
        with lock:active-=1
    def sync(i:int)->str:
        enter()
        try:time.sleep(.06);return str(i)
        finally:leave()
    async def work(i:int)->str:
        enter()
        try:await asyncio.sleep(.06);return str(i)
        finally:leave()
    async def async_tool(i:int)->str:
        if guarded:
            async with gate:return await work(i)
        return await work(i)
    t=StructuredTool.from_function(func=sync if kind=="sync" else None,coroutine=async_tool if kind=="async" else None,name="probe",description="Synthetic read-only delay")
    b=StateGraph(MessagesState);b.add_node("tools",ToolNode([t]));b.add_edge(START,"tools");b.add_edge("tools",END)
    graph=b.compile()
    inputs={"messages":[AIMessage(content="",tool_calls=[{"name":"probe","args":{"i":i},"id":f"c{i}"} for i in range(n)])]}
    start=time.perf_counter()
    config={"max_concurrency":limit}
    result=graph.invoke(inputs,config=config) if mode=="invoke" else await graph.ainvoke(inputs,config=config)
    outputs=[x for x in result["messages"] if isinstance(x,ToolMessage)]
    assert len(outputs)==n and {x.tool_call_id for x in outputs}=={f"c{i}" for i in range(n)} and {x.content for x in outputs}=={str(i) for i in range(n)}
    assert active==0
    return {"tool":kind,"entry":mode,"limit":limit,"guarded":guarded,"peak":peak,"outputs":len(outputs),"respected":peak<=limit,"elapsed_seconds":round(time.perf_counter()-start,4)}
async def main():
    rows=[]
    for limit in (1,2,4):
        for kind,mode,guarded in (("sync","invoke",False),("sync","ainvoke",False),("async","ainvoke",False),("async","ainvoke",True)):
            rows.append(await run(kind,mode,limit,guarded))
    for r in rows:
        expected=r["limit"] if r["entry"]=="invoke" or r["guarded"] else 4
        assert r["peak"]==expected,(r,expected)
    payload={"date":"2026-11-25","python":sys.version.split()[0],"os":platform.platform(),"versions":{p:version(p) for p in ("langgraph","langgraph-prebuilt","langchain-core","langgraph-checkpoint","langgraph-sdk")},"scope":"four synthetic calls in one hand-built StateGraph ToolNode; async-only resource guard; no create_agent or real service test","source_async_gather":"asyncio.gather" in inspect.getsource(ToolNode._afunc),"cases":rows,"assertions_passed":len(rows)}
    print(json.dumps(payload,indent=2))
    Path(__file__).with_name("results").joinpath("repro-1.2.22-20261125.json").write_text(json.dumps(payload,indent=2)+"\n")
if __name__=="__main__":asyncio.run(main())
