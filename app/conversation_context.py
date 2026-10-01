MAX_CONTEXT_MESSAGES = 40
MAX_CONTEXT_CHARS = 12000

def build_context(messages, system_prompt="", max_messages=MAX_CONTEXT_MESSAGES, max_chars=MAX_CONTEXT_CHARS):
    result = [{"role": "system", "content": str(system_prompt)}] if system_prompt else []
    context = []
    used = 0
    for message in reversed(messages[-max_messages:]):
        role = message.get("role")
        content = str(message.get("content", ""))
        if role not in ("user", "assistant") or not content:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[-remaining:]
        context.append({"role": role, "content": content})
        used += len(content)
    result.extend(reversed(context))
    return result
