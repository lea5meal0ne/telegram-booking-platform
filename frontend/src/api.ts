import i18n from "./i18n";
export type Localized = { ru: string; en?: string };
export interface User {
  id: number;
  name: string;
  language: "ru" | "en";
  is_admin: boolean;
  deletion_requested: boolean;
}
export interface Service {
  id: number;
  name: Localized;
  description: Localized;
  price: number;
  currency: string;
  duration: number;
  active: boolean;
  image: string;
  position: number;
}
export interface Appointment {
  id: number;
  service_id: number;
  user_id: number;
  start: string;
  end: string;
  status: string;
  snapshot: {
    name: Localized;
    price: number;
    currency: string;
    duration: number;
  };
  customer_confirmed: boolean;
  admin_confirmed: boolean;
  verified_at: string | null;
  customer_name?: string;
}
export interface Portfolio {
  id: number;
  category_id: number | null;
  description: Localized;
  images: string[];
  position: number;
}
export interface Category {
  id: number;
  name: Localized;
}
export interface Review {
  id: number;
  rating: number;
  text: string;
  name?: string;
  at: string;
  visible: boolean;
  anonymous: boolean;
}
export interface Conversation {
  id: number;
  user_id: number;
  status: string;
  name?: string;
}
export interface Message {
  id: number;
  sender_id: number;
  text: string;
  image: string;
  at: string;
}
export interface Schedule {
  id?: number;
  weekday: number | null;
  date: string | null;
  start: string;
  end: string;
  blocked: boolean;
}
export interface Business {
  name: Localized;
  description: Localized;
  timezone: string;
  currency: string;
  accent: string;
  address: string;
  phone: string;
  telegram: string;
  website: string;
  social_links: string[];
  logo: string;
  cover: string;
  horizon_days: number;
  notice_minutes: number;
  cancel_minutes: number;
  slot_minutes: number;
  buffer_minutes: number;
  reminder_hours: number;
}
let token = sessionStorage.getItem("booking-session") || "";
export function setToken(value: string) {
  token = value;
  sessionStorage.setItem("booking-session", value);
}
export function clearToken() {
  token = "";
  sessionStorage.removeItem("booking-session");
}
export function getToken() {
  return token;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const result = await fetch("/api" + path, {
    ...options,
    headers: {
      "Accept-Language": i18n.language,
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!result.ok) {
    const error = await result.json().catch(() => ({}));
    throw new Error(error.message || `HTTP ${result.status}`);
  }
  return result.json();
}
export function post<T>(path: string, body: unknown = {}) {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
export function put<T>(path: string, body: unknown) {
  return api<T>(path, { method: "PUT", body: JSON.stringify(body) });
}
export async function upload(file: File) {
  const body = new FormData();
  body.append("file", file);
  return (await api<{ url: string }>("/uploads", { method: "POST", body })).url;
}
export async function privateImage(url: string) {
  const response = await fetch(
    url.replace("/api/media/", "/api/private-media/"),
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) throw new Error("Image unavailable");
  return URL.createObjectURL(await response.blob());
}
