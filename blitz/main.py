import blitzApp as blitzApp
from utils import get_config

from contextlib import asynccontextmanager
from http import HTTPStatus
from fastapi import FastAPI, Request, Response
import uvicorn

'''
Every app in APPS must have
bot: Application
endpoint: str
async def setup() -> None
async def process_request() -> Response
'''
APPS = [blitzApp]

@asynccontextmanager
async def lifespan(_: FastAPI):
    for app in APPS:
        await app.setup()
        async with app.bot:
            await app.bot.start()
            yield
            await app.bot.stop()

# Initialize FastAPI app (similar to Flask)
webserver = FastAPI(lifespan=lifespan)

@webserver.get('/webhook/test')
async def test_webapp(request: Request) -> Response:
    # Test with below urls
    # https://localhost:80/test
    return Response("All is good!", status_code=HTTPStatus.OK)

for app in APPS:
    async def process_request(request: Request):
        return await app.process_request(request)
    webserver.add_api_route(app.endpoint, process_request, methods=['POST'])

if __name__ == '__main__':
    uvicorn.run(
        "main:webserver",
        host='0.0.0.0',
        port=get_config("port"),
    )
