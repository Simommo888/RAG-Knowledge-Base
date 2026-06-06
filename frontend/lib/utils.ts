import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number | null | undefined) {
  return Number(value || 0).toLocaleString("zh-CN");
}

export function formatDate(value?: string | null) {
  if (!value) return "暂无";
  try {
    return new Date(value).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return value;
  }
}

export function compactText(value: string, max = 180) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max)}...` : clean;
}
