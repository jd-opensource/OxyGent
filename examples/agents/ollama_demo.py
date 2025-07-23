"""gemma_cli_demo.py
"""

import asyncio
from oxygent import MAS, oxy  
from oxygent.utils.env_utils import get_env_var

oxy_space = [
    oxy.HttpLLM(                
        name="local_gemma",  
        base_url="http://localhost:11434/api/chat", 
        model_name=get_env_var("DEFAULT_OLLAMA_MODEL"),   
        llm_params={"temperature": 0.2},    
        semaphore=1,              
        timeout=240,
    ),

    oxy.ChatAgent(
        name="master_agent",
        is_master=True,
        llm_model="local_gemma",  
    ),
]

async def chat():
    async with MAS(oxy_space=oxy_space) as mas:
        history = [{"role": "system", "content": "You are a helpful assistant."}]

        while True:
            user_in = input("User: ").strip()
            if user_in.lower() in {"exit", "quit", "q"}:
                break

            history.append({"role": "user", "content": user_in})
            result = await mas.call(
                callee="master_agent",
                arguments={"messages": history},
            )
            assistant_out = result
            print(f"Assistant: {assistant_out}\n")
            history.append({"role": "assistant", "content": assistant_out})

if __name__ == "__main__":
    asyncio.run(chat())
