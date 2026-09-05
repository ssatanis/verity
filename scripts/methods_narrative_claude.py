#!/usr/bin/env python3
"""Plain-language narrative for docs/methods.md: for each section, Claude writes three to five sentences from the section's own text
and numbers only (no new facts, no conclusions about providers). Inserted as a paragraph starting 'In plain language.' under the header;
re-running replaces the previous narrative."""
import os, re, sys
from pydantic import BaseModel, Field
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "api")
import llm
class Narrative(BaseModel):
    text: str = Field(description="Three to five plain-English sentences that explain what this section measures, how, and what the numbers say, using only facts in the section. No em dashes. Do not name providers.")
SYS = "You write plain-language explanations of statistical methods for a program-integrity audience. Use only the section text. Say what was measured, how, and what the numbers show, including the caveats the section states. Never add facts, never name providers, never assert fraud. Short sentences. No em dashes."
s = open("docs/methods.md").read()
parts = re.split(r"(?m)^(## .+)$", s)
out = [parts[0]]
for i in range(1, len(parts), 2):
    header, body = parts[i], parts[i + 1]
    body = re.sub(r"\n\*\*In plain language\.\*\*[^\n]*\n", "\n", body)
    try:
        n = llm.parse(Narrative, SYS, f"Section header: {header}\n\n{body[:14000]}", effort="medium").text.strip()
        body = "\n\n**In plain language.** " + n + "\n" + body
        print("narrated", header)
    except Exception as e: print("skipped", header, str(e)[:80])
    out += [header, body]
open("docs/methods.md", "w").write("".join(out)); print("methods.md updated")
