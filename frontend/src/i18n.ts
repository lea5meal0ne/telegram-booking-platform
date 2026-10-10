import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ru from "./locales/ru.json";
import en from "./locales/en.json";
import type { Localized } from "./api";
i18n.use(initReactI18next).init({
  resources: { ru: { translation: ru }, en: { translation: en } },
  lng: "ru",
  fallbackLng: "ru",
  interpolation: { escapeValue: false },
});
export function content(value: Localized | undefined) {
  return value?.[i18n.language as "ru" | "en"] || value?.ru || "";
}
export function money(price: number, currency: string) {
  return new Intl.NumberFormat(i18n.language, {
    style: "currency",
    currency,
  }).format(price / 100);
}
export function dateTime(value: string, timezone = "Europe/Moscow") {
  return new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: timezone,
  }).format(new Date(value));
}
export default i18n;
