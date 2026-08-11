export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

export type CurrentUser = { id: string; full_name: string; phone: string; email?: string; role: "owner" | "manager" | "staff"; active: boolean };

export async function getCurrentUser(cookie?: string): Promise<CurrentUser | null> {
  try {
    const serverBase = process.env.BACKEND_URL ? `${process.env.BACKEND_URL}/api/v1` : "http://localhost:8000/api/v1";
    const response = await fetch(`${serverBase}/auth/me`, { headers: cookie ? { cookie } : {}, credentials: "include", cache: "no-store" });
    return response.ok ? response.json() : null;
  } catch { return null; }
}

export async function serverGet<T>(path: string, cookie: string): Promise<T> {
  const serverBase = process.env.BACKEND_URL ? `${process.env.BACKEND_URL}/api/v1` : "http://localhost:8000/api/v1";
  const response = await fetch(`${serverBase}${path}`, { headers: { cookie }, cache: "no-store" });
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return response.json();
}

export async function serverGetOptional<T>(path: string, cookie: string): Promise<T | null> {
  const serverBase = process.env.BACKEND_URL ? `${process.env.BACKEND_URL}/api/v1` : "http://localhost:8000/api/v1";
  const response = await fetch(`${serverBase}${path}`, { headers: { cookie }, cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return response.json();
}
