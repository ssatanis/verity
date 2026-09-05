"""Shared Anthropic client for Verity. Models: claude-opus-5 for drafting and adjudication, claude-haiku-4-5 only where the caller
asks for the cheap tier explicitly. Every helper strips em dashes from model text (house style) and never lets the model invent facts:
callers pass evidence rows and the schemas force citations."""
import json, os, re
from typing import Type, TypeVar
import anthropic
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
MODEL = os.environ.get("VERITY_MODEL", "claude-opus-5")
MODEL_FAST = os.environ.get("VERITY_MODEL_FAST", "claude-haiku-4-5")
T = TypeVar("T", bound=BaseModel)
_client = None
def client() -> anthropic.Anthropic:
    global _client
    if _client is None: _client = anthropic.Anthropic()
    return _client
def ready() -> bool:
    k = os.environ.get("ANTHROPIC_API_KEY", ""); return k.startswith("sk-ant-")
DASHES = {"—": ", ", "–": " to ", "‒": "-", "―": ", "}
def clean_text(s):
    """House style: no em or en dashes anywhere in model output."""
    if isinstance(s, str):
        for k, v in DASHES.items(): s = s.replace(k, v)
        return re.sub(r"\s+,", ",", s)
    if isinstance(s, list): return [clean_text(x) for x in s]
    if isinstance(s, dict): return {k: clean_text(v) for k, v in s.items()}
    return s
def parse(schema: Type[T], system: str, user: str, model: str = None, effort: str = "high", max_tokens: int = 16000) -> T:
    """Structured output validated against a Pydantic schema. Uses adaptive thinking; thinking is billed but not returned."""
    r = client().messages.parse(model=model or MODEL, max_tokens=max_tokens, system=system, output_config={"effort": effort},
                                messages=[{"role": "user", "content": user}], output_format=schema)
    if r.stop_reason == "refusal": raise RuntimeError(f"model refused: {getattr(r.stop_details, 'explanation', '')}")
    out = r.parsed_output
    return schema.model_validate(clean_text(out.model_dump()))
def text(system: str, user: str, model: str = None, effort: str = "medium", max_tokens: int = 8000) -> str:
    r = client().messages.create(model=model or MODEL, max_tokens=max_tokens, system=system, output_config={"effort": effort}, messages=[{"role": "user", "content": user}])
    if r.stop_reason == "refusal": raise RuntimeError("model refused")
    return clean_text("".join(b.text for b in r.content if b.type == "text"))
def batch_requests(items, schema: Type[T], system: str, model: str = None, effort: str = "medium", max_tokens: int = 4000):
    """Build Message Batches API requests with a JSON schema output format. items: iterable of (custom_id, user_text)."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    fmt = {"type": "json_schema", "schema": schema.model_json_schema()}
    return [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(model=model or MODEL, max_tokens=max_tokens, system=system, output_config={"effort": effort, "format": fmt},
                                                                          messages=[{"role": "user", "content": txt}])) for cid, txt in items]
def batch_run(requests, poll_seconds=30, max_wait=6 * 3600):
    """Submit a batch and wait for it. Returns {custom_id: parsed JSON or {'error': ...}}."""
    import time
    b = client().messages.batches.create(requests=requests); t0 = time.time()
    while True:
        b = client().messages.batches.retrieve(b.id)
        if b.processing_status == "ended": break
        if time.time() - t0 > max_wait: raise TimeoutError(b.id)
        time.sleep(poll_seconds)
    out = {}
    for res in client().messages.batches.results(b.id):
        if res.result.type == "succeeded":
            txt = "".join(blk.text for blk in res.result.message.content if blk.type == "text")
            try: out[res.custom_id] = clean_text(json.loads(txt))
            except Exception as e: out[res.custom_id] = {"error": f"unparseable: {e}", "raw": txt[:200]}
        else: out[res.custom_id] = {"error": res.result.type}
    return out, b.id
