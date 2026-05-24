import json
import logging
import httpx
from fastapi import APIRouter, HTTPException
from .schemas import PromptIn

logger = logging.getLogger(__name__)
chatbot_router = APIRouter()

try:
	from ...core.ai_client import ai_client
except Exception:
	try:
		from core.ai_client import ai_client
	except Exception:
		# Fallback: attempt to load module by path so running uvicorn from
		# within the package dir still works (avoids "attempted relative
		# import beyond top-level package" and ModuleNotFoundError).
		import os, sys, importlib.util
		try:
			this_dir = os.path.dirname(os.path.abspath(__file__))
			package_root = os.path.dirname(this_dir)  # ai_service/
			core_path = os.path.join(package_root, 'core', 'ai_client.py')
			if os.path.exists(core_path):
				spec = importlib.util.spec_from_file_location('core.ai_client', core_path)
				mod = importlib.util.module_from_spec(spec)
				spec.loader.exec_module(mod)
				ai_client = getattr(mod, 'ai_client', None)
			else:
				# As a last resort, try adding package_root parent to sys.path
				sys.path.insert(0, package_root)
				try:
					from core.ai_client import ai_client
				except Exception as e:
					logger.exception("Could not import FastAPI ai_client: %s", e)
					ai_client = None
		except Exception as e:
			logger.exception("Could not import FastAPI ai_client via fallback: %s", e)
			ai_client = None


@chatbot_router.post("/")
async def chatbot_endpoint(payload: PromptIn):
	if not payload or not payload.prompt:
		raise HTTPException(status_code=400, detail="Missing prompt")

	if ai_client is None:
		raise HTTPException(status_code=503, detail="AI service not available")

	try:
		async with httpx.AsyncClient(timeout=30) as client:
			raw = await ai_client.generate_content(client, payload.prompt, payload.max_tokens)

		# Normalize response
		if isinstance(raw, dict):
			if "response" in raw:
				content = raw.get("response", "")
			elif "choices" in raw:
				choices = raw.get("choices")
				if isinstance(choices, list) and choices:
					first = choices[0]
					content = first.get("text") or (first.get("message") or {}).get("content", "")
				else:
					content = json.dumps(raw)
			else:
				content = json.dumps(raw)
		else:
			content = str(raw)

		return {"response": content}

	except Exception as exc:
		logger.exception("Error in FastAPI chatbot endpoint: %s", exc)
		raise HTTPException(status_code=500, detail="AI service error")
