"""Agent runtime — the layer above syncing.

Sync collects, analyzers judge, and this reads both, investigates what looks
wrong, and says what to do about it. It has no write access to any ad platform;
its output is a written finding and an alert.

Execution comes later, and deliberately not yet: the record from analysing this
business by hand was eight correct discoveries against two of four correct
budget calls. The discovery work earns autonomy first.
"""

import json

import frappe

from growth_portal.agent import prompt as agent_prompt
from growth_portal.agent import tools as agent_tools

MODEL = "claude-opus-5"
EFFORT = "high"          # sweep medium/xhigh once there is a run history to compare
MAX_TOKENS = 32000


def _client():
    import anthropic

    key = frappe.conf.get("anthropic_api_key")
    if not key:
        frappe.throw("anthropic_api_key is not set in site_config.json")
    return anthropic.Anthropic(api_key=key)


@frappe.whitelist()
def run(task="daily", context=None, notify=True):
    """One investigation. Returns the Agent Run name."""
    client = _client()
    instruction = agent_prompt.TASKS.get(task, task)
    if context:
        instruction += "\n\n" + (context if isinstance(context, str) else json.dumps(context, ensure_ascii=False))

    run_doc = frappe.get_doc({
        "doctype": "Agent Run", "task": task, "status": "Running",
        "model": MODEL, "effort": EFFORT,
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    trace, finding = [], ""
    try:
        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": EFFORT},
            # Frozen prefix, cached. Nothing dynamic is interpolated into it —
            # a timestamp in the system prompt would invalidate the cache on
            # every single run.
            system=[{
                "type": "text",
                "text": agent_prompt.SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=agent_tools.TOOLS,
            messages=[{"role": "user", "content": instruction}],
            # Safety classifiers can decline; without a fallback the request
            # simply stops and the run silently produces nothing.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

        for message in runner:
            for block in message.content:
                if block.type == "tool_use":
                    trace.append({"tool": block.name, "input": block.input})
                elif block.type == "text" and block.text:
                    finding = block.text

            if message.stop_reason == "refusal":
                run_doc.db_set("status", "Refused")
                break

        run_doc.db_set({
            "status": run_doc.status if run_doc.status == "Refused" else "Done",
            "finding": finding,
            "tool_calls": json.dumps(trace, ensure_ascii=False, default=str),
            "tool_call_count": len(trace),
        })
        frappe.db.commit()

        if notify and finding and run_doc.status == "Done":
            from growth_portal.notify import dispatch
            dispatch.send_finding(run_doc.name, task, finding)

    except Exception:
        run_doc.db_set({"status": "Failed", "finding": frappe.get_traceback()[:4000]})
        frappe.db.commit()
        raise

    return run_doc.name


@frappe.whitelist()
def daily():
    """Scheduled entry point."""
    return run(task="daily")


@frappe.whitelist()
def integrity():
    return run(task="integrity")
