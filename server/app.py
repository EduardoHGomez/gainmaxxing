from fastapi import FastAPI

from agent.graph import graph  

app = FastAPI(title="agent-server")

@app.get("/health")
async def health():
    return {"ok": True}


