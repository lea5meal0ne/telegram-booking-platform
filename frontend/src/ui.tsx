import { useEffect, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, privateImage, upload } from "./api";
import type { Localized } from "./api";

export function Empty({ text }: { text?: string }) {
  const { t } = useTranslation();
  return <div className="empty">{text || t("empty")}</div>;
}
export function Loading() {
  return (
    <div aria-busy="true" className="skeleton">
      <div />
      <div />
      <div />
    </div>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
export function LocalizedFields({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: Localized;
  onChange: (value: Localized) => void;
  multiline?: boolean;
}) {
  const { t } = useTranslation();
  const Input = multiline ? "textarea" : "input";
  return (
    <div className="two-col">
      {(["ru", "en"] as const).map((l) => (
        <Field
          key={l}
          label={`${label} · ${t(l === "ru" ? "ruContent" : "enContent")}`}
        >
          <Input
            value={value[l] || ""}
            onChange={(e) => onChange({ ...value, [l]: e.target.value })}
            required={l === "ru" && !multiline}
          />
        </Field>
      ))}
    </div>
  );
}
export function Upload({
  value,
  onChange,
  multiple = false,
  onError,
}: {
  value: string[];
  onChange: (urls: string[]) => void;
  multiple?: boolean;
  onError: (message: string) => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const previewRefs = useRef<string[]>([]);
  useEffect(
    () => () => previewRefs.current.forEach((url) => URL.revokeObjectURL(url)),
    [],
  );
  return (
    <div>
      <label className="button secondary">
        {busy ? t("loading") : t("attach")}
        <input
          hidden
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple={multiple}
          disabled={busy}
          onChange={async (e) => {
            const files = Array.from(e.target.files || []);
            setBusy(true);
            try {
              const urls = [];
              for (const file of files) {
                const url = await upload(file);
                urls.push(url);
                const preview = URL.createObjectURL(file);
                previewRefs.current.push(preview);
                setPreviews((previous) => ({ ...previous, [url]: preview }));
              }
              onChange(multiple ? [...value, ...urls] : urls);
            } catch (error) {
              onError((error as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        />
      </label>
      <div className="gallery">
        {value.map((url) => (
          <img key={url} src={previews[url] || url} alt={t("preview")} />
        ))}
      </div>
      <div className="chips">
        {value.map((url, index) => (
          <button
            type="button"
            className="secondary"
            key={url}
            onClick={() => onChange(value.filter((_, i) => i !== index))}
          >
            {t("image")} {index + 1} ×
          </button>
        ))}
      </div>
    </div>
  );
}
export function ProtectedImage({ url }: { url: string }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let live = true;
    let object = "";
    privateImage(url)
      .then((value) => {
        object = value;
        if (live) setSrc(value);
      })
      .catch(() => {});
    return () => {
      live = false;
      if (object) URL.revokeObjectURL(object);
    };
  }, [url]);
  return src ? <img className="attachment" src={src} alt="" /> : null;
}
export function Calendar({
  serviceId,
  appointmentId,
  timezone,
  selected,
  onSelect,
  month,
  setMonth,
}: {
  serviceId: number;
  appointmentId?: number;
  timezone: string;
  selected: string;
  onSelect: (date: string) => void;
  month: string;
  setMonth: (month: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const query = useQuery({
    queryKey: ["availability-month", serviceId, month, appointmentId],
    queryFn: () =>
      api<Record<string, number>>(
        appointmentId
          ? `/appointments/${appointmentId}/availability/month?month=${month}-01`
          : `/availability/month?service_id=${serviceId}&month=${month}-01`,
      ),
  });
  const [year, m] = month.split("-").map(Number);
  const days = new Date(year, m, 0).getDate();
  const offset = (new Date(year, m - 1, 1).getDay() + 6) % 7;
  function change(delta: number) {
    const value = new Date(year, m - 1 + delta, 1);
    setMonth(
      `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}`,
    );
  }
  const weekdays = Array.from({ length: 7 }, (_, i) =>
    new Intl.DateTimeFormat(i18n.language, { weekday: "short" }).format(
      new Date(2024, 0, 1 + i),
    ),
  );
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  return (
    <section className="card calendar">
      <div className="calendar-heading">
        <button
          type="button"
          className="icon-button"
          aria-label={t("previousMonth")}
          onClick={() => change(-1)}
        >
          <ChevronLeft />
        </button>
        <strong>
          {new Intl.DateTimeFormat(i18n.language, {
            month: "long",
            year: "numeric",
          }).format(new Date(year, m - 1, 1))}
        </strong>
        <button
          type="button"
          className="icon-button"
          aria-label={t("nextMonth")}
          onClick={() => change(1)}
        >
          <ChevronRight />
        </button>
      </div>
      <div className="calendar-grid">
        {weekdays.map((d, i) => (
          <span key={i} className="weekday">
            {d}
          </span>
        ))}
        {Array.from({ length: offset }, (_, i) => (
          <span key={`blank${i}`} />
        ))}
        {Array.from({ length: days }, (_, i) => {
          const key = `${month}-${String(i + 1).padStart(2, "0")}`;
          const count = query.data?.[key] || 0;
          return (
            <button
              type="button"
              key={key}
              aria-label={`${key}: ${t(count ? "available" : key < today ? "unavailable" : "full")}`}
              disabled={!count || query.isLoading}
              className={`${key === selected ? "selected" : ""} ${count ? "available" : ""}`}
              onClick={() => onSelect(key)}
            >
              {i + 1}
              {count > 0 && <i />}
            </button>
          );
        })}
      </div>
      {query.isLoading && <Loading />}
      {query.isError && <p role="alert">{t("error")}</p>}
      <small>{t("notice", { timezone })}</small>
    </section>
  );
}
export function ImageViewer({
  images,
  index,
  onClose,
}: {
  images: string[];
  index: number;
  onClose: () => void;
}) {
  const [current, setCurrent] = useState(index);
  const { t } = useTranslation();
  return (
    <div className="viewer" role="dialog" aria-modal="true">
      <button aria-label={t("close")} onClick={onClose}>
        <X />
      </button>
      <img src={images[current]} alt="" />
      <div>
        <button
          aria-label={t("back")}
          onClick={() =>
            setCurrent((current + images.length - 1) % images.length)
          }
        >
          <ChevronLeft />
        </button>
        <span>
          {current + 1} / {images.length}
        </span>
        <button
          aria-label={t("next")}
          onClick={() => setCurrent((current + 1) % images.length)}
        >
          <ChevronRight />
        </button>
      </div>
    </div>
  );
}

export function Pager({
  offset,
  count,
  onChange,
}: {
  offset: number;
  count: number;
  onChange: (offset: number) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="actions">
      <button
        className="secondary"
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - 50))}
      >
        {t("back")}
      </button>
      <button
        className="secondary"
        disabled={count < 50}
        onClick={() => onChange(offset + 50)}
      >
        {t("next")}
      </button>
    </div>
  );
}
