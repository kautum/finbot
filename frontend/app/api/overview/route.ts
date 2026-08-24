// Proxies the agent's dataset overview so the browser never needs the backend's address.
const AGENT_URL = process.env.AGENT_URL || "http://localhost:8123";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await fetch(`${AGENT_URL}/overview`, { cache: "no-store" });
    if (!res.ok) throw new Error(`agent responded ${res.status}`);
    return Response.json(await res.json());
  } catch (e) {
    // The panel degrades to a quiet placeholder rather than breaking the chat.
    return Response.json(
      { error: e instanceof Error ? e.message : "agent unreachable" },
      { status: 503 },
    );
  }
}
