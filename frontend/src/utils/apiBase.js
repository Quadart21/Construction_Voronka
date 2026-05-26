export function getApiBase() {
  const raw = import.meta.env.VITE_API_BASE;
  if (raw != null && String(raw).trim() !== "") {
    return String(raw).trim().replace(/\/$/, "");
  }
  return "/api";
}
