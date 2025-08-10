.PHONY: run


run:
	uv run uvicorn settings.asgi:application --reload --host 0.0.0.0 --port 8000