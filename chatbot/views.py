import json
import asyncio
from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from langchain_cohere import ChatCohere
# from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.callbacks.base import AsyncCallbackHandler
import os
from dotenv import load_dotenv

load_dotenv()

class AsyncStreamingCallbackHandler(AsyncCallbackHandler):
    """Async callback handler for streaming responses"""
    def __init__(self, queue):
        self.queue = queue
        self.streaming_complete = False
    
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        await self.queue.put(token)
    
    async def on_llm_end(self, response, **kwargs) -> None:
        self.streaming_complete = True
        await self.queue.put(None)  # Signal end of stream

def index(request):
    """Render the main chat interface"""
    return render(request, 'chatbot/index.html')

async def event_stream(message):
    """Generate SSE events from LangChain streaming response"""
    queue = asyncio.Queue()
    callback = AsyncStreamingCallbackHandler(queue)
    
    # Initialize LangChain
    llm = ChatCohere(
        model="command-r-plus",
        callbacks=[callback],
        streaming=True,
        temperature=0.7
    )
    
    # Create conversation
    messages = [
        SystemMessage(content="You are a helpful AI assistant."),
        HumanMessage(content=message)
    ]
    
    # Start generating response
    task = asyncio.create_task(llm.ainvoke(messages))
    
    try:
        while True:
            # Get token from queue
            token = await asyncio.wait_for(queue.get(), timeout=30)
            
            if token is None:  # End of stream
                yield f"data: [DONE]\n\n"
                break
            
            # Format as SSE
            data = json.dumps({"content": token})
            yield f"data: {data}\n\n"
            
    except asyncio.TimeoutError:
        yield f"data: {json.dumps({'error': 'Response timeout'})}\n\n"
        yield f"data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: [DONE]\n\n"
    finally:
        # Ensure task completes
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

@csrf_exempt
async def chat_stream(request):
    """Handle chat requests with SSE streaming"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            
            response = StreamingHttpResponse(
                event_stream(message),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            response['Connection'] = 'keep-alive'
            return response
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
