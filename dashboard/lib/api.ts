const API =
  process.env.NEXT_PUBLIC_API_URL === "same-origin"
    ? ""
    : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const KEY = process.env.NEXT_PUBLIC_API_KEY || "change-me-demo-key";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": KEY,
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export function streamUrl(): string {
  return `${API}/api/v1/stream/events?api_key=${encodeURIComponent(KEY)}`;
}

export { API };
