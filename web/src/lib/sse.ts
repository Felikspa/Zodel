export type SseMessage =
  | { type: "start" }
  | { type: "delta"; text: string }
  | { type: "done" }
  | { type: "error"; message: string }
  | { type: "model_info"; model: string };

function parseSseLines(buffer: string): { events: string[]; rest: string } {
  // SSE events separated by blank line.
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  return { events: parts, rest };
}

function parseEventBlock(block: string): { event: string; data: string } | null {
  const lines = block.split("\n");
  let event = "message";
  let data = "";
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line) continue;
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      data += line.slice("data:".length).trim();
      continue;
    }
  }
  if (!data) return null;
  return { event, data };
}

export async function* fetchSse(
  url: string,
  init: RequestInit
): AsyncGenerator<SseMessage, void, unknown> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {})
    }
  });

  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const { events, rest } = parseSseLines(buffer);
    buffer = rest;

    for (const block of events) {
      const parsed = parseEventBlock(block);
      if (!parsed) continue;
      try {
        const msg = JSON.parse(parsed.data) as SseMessage;
        yield msg;
      } catch {
        // ignore malformed events
      }
    }
  }
}

