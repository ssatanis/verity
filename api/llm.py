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
def clean_text(x):
    """Strip em and en dashes from any string, list or dict (house style: no dashes, not even in packets)."""
    if isinstance(x, str):
        for k, v in DASHES.items(): x = x.replace(k, v)
        return re.sub(r"[ \t]{2,}", " ", re.sub(r"\s+,", ",", x))
    if isinstance(x, list): return [clean_text(v) for v in x]
    if isinstance(x, dict): return {k: clean_text(v) for k, v in x.items()}
    return x

def parse(schema: Type[T], system: str, user: str, model: str = None, effort: str = "high", max_tokens: int = 16000) -> T:
    """Structured output: returns an instance of the Pydantic schema. Raises RuntimeError on refusal or empty output."""
    r = client().messages.parse(model=model or MODEL, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}],
                                output_config={"effort": effort}, output_format=schema)
    if r.stop_reason == "refusal" or r.parsed_output is None: raise RuntimeError(f"model returned no structured output (stop_reason={r.stop_reason})")
    return r.parsed_output

def text(system: str, user: str, model: str = None, effort: str = "medium", max_tokens: int = 8000) -> str:
    """Plain text completion with the house dash rule applied."""
    r = client().messages.create(model=model or MODEL, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}], output_config={"effort": effort})
    return clean_text("".join(b.text for b in r.content if getattr(b, "type", "") == "text"))

def strict_schema(schema: dict) -> dict:
    """The structured-output endpoint requires additionalProperties=false on every object; Pydantic's model_json_schema omits it."""
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "additionalProperties" not in node: node["additionalProperties"] = False
            for v in node.values(): walk(v)
        elif isinstance(node, list):
            for v in node: walk(v)
    walk(schema); return schema

def batch_requests(items, schema: Type[T], system: str, model: str = None, effort: str = "medium", max_tokens: int = 4000):
    """Build Message Batches API requests with a JSON schema output format. items: iterable of (custom_id, user_text)."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    fmt = {"type": "json_schema", "schema": strict_schema(schema.model_json_schema())}
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
