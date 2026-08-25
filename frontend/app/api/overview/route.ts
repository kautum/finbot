// Proxies the agent's dataset overview so the browser never needs the backend's address.
import snapshot from "../../lib/overview-snapshot.json";

const AGENT_URL = process.env.AGENT_URL || "http://localhost:8123";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await fetch(`${AGENT_URL}/overview`, { cache: "no-store" });
    if (!res.ok) throw new Error(`agent responded ${res.status}`);
    return Response.json(await res.json());
  } catch {
    // No backend reachable -- serve the committed snapshot instead of a 503, so the
    // deployed page still shows the real catalogue. Every figure in it was measured by
    // agent/catalog.py against the actual database; regenerate it with
    // `python -m catalog` rather than editing by hand.
    // `snapshot: true` is what the UI keys off to say the chat is offline. Without it the
    // page would look fully working right up until someone typed a question.
    return Response.json({ ...snapshot, snapshot: true });
  }
}
