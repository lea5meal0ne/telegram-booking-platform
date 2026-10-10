import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api, post, put } from "./api";
import type {
  Appointment,
  Service,
  Portfolio,
  Category,
  Review,
  Schedule,
  Business,
  Conversation,
} from "./api";
import { content, dateTime, money } from "./i18n";
import { useApp } from "./App";
import { Loading, Empty, Field, LocalizedFields, Upload } from "./ui";
import { SupportThread } from "./pages";

const tabs = [
  "dashboard",
  "schedule",
  "appointments",
  "services",
  "portfolio",
  "reviews",
  "messages",
  "settings",
];
export default function Admin() {
  const { t } = useTranslation();
  const [tab, setTab] = useState("dashboard");
  return (
    <>
      <div className="section-title">
        <h1>{t("admin")}</h1>
      </div>
      <nav className="admin-tabs">
        {tabs.map((key) => (
          <button
            key={key}
            className={tab === key ? "" : "secondary"}
            onClick={() => setTab(key)}
          >
            {t(key)}
          </button>
        ))}
      </nav>
      {tab === "dashboard" ? (
        <Dashboard />
      ) : tab === "services" ? (
        <Services />
      ) : tab === "schedule" ? (
        <ScheduleEditor />
      ) : tab === "appointments" ? (
        <AppointmentManager />
      ) : tab === "portfolio" ? (
        <PortfolioManager />
      ) : tab === "reviews" ? (
        <ReviewManager />
      ) : tab === "messages" ? (
        <Inbox />
      ) : (
        <SettingsEditor />
      )}
    </>
  );
}
function useAdmin<T>(key: string, path: string) {
  return useQuery({ queryKey: ["admin", key], queryFn: () => api<T>(path) });
}
function useActions() {
  const { t } = useTranslation();
  const { notify } = useApp();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<unknown>, done?: () => void) {
    setBusy(true);
    try {
      await fn();
      await client.invalidateQueries();
      notify(t("saved"));
      done?.();
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return { run, busy, notify };
}
function Dashboard() {
  const { t } = useTranslation();
  const data = useAdmin<Record<string, number>>(
    "dashboard",
    "/admin/dashboard",
  );
  const failures = useAdmin<{ id: number; kind: string; attempts: number }[]>(
    "notifications",
    "/admin/notifications",
  );
  const requests = useAdmin<{ id: number; name: string }[]>(
    "deletion-requests",
    "/admin/deletion-requests",
  );
  const { run } = useActions();
  return (
    <>
      {data.isLoading ? (
        <Loading />
      ) : (
        <div className="stats-grid">
          {data.data &&
            Object.entries(data.data).map(([key, value]) => (
              <section className="card stat" key={key}>
                <span>{t(key)}</span>
                <strong>{key === "rating" ? value.toFixed(1) : value}</strong>
              </section>
            ))}
        </div>
      )}
      {!!failures.data?.length && (
        <section className="card">
          <h2>{t("notifications")}</h2>
          {failures.data.map((job) => (
            <div className="rule" key={job.id}>
              <span>
                #{job.id} · {t(job.kind)}
              </span>
              <button
                className="secondary"
                onClick={() =>
                  run(() => post(`/admin/notifications/${job.id}/retry`))
                }
              >
                {t("retry")}
              </button>
            </div>
          ))}
        </section>
      )}
      {!!requests.data?.length && (
        <section className="card">
          <h2>{t("deletionRequests")}</h2>
          {requests.data.map((user) => (
            <p key={user.id}>
              {user.name} · {user.id}
            </p>
          ))}
        </section>
      )}
    </>
  );
}
const newService = (): Omit<Service, "id"> => ({
  name: { ru: "", en: "" },
  description: { ru: "", en: "" },
  price: 0,
  duration: 60,
  currency: "RUB",
  active: true,
  position: 0,
  image: "",
});
function Services() {
  const { t } = useTranslation();
  const data = useAdmin<Service[]>("services", "/admin/services");
  const [draft, setDraft] = useState<Partial<Service> | null>(null);
  const { run, busy, notify } = useActions();
  function patch(values: Partial<Service>) {
    setDraft({ ...draft, ...values });
  }
  return (
    <>
      <div className="section-title">
        <h2>{t("services")}</h2>
        <button onClick={() => setDraft(newService())}>{t("new")}</button>
      </div>
      {draft && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            run(
              () =>
                draft.id
                  ? put(`/admin/services/${draft.id}`, draft)
                  : post("/admin/services", draft),
              () => setDraft(null),
            );
          }}
        >
          <LocalizedFields
            label={t("name")}
            value={draft.name!}
            onChange={(name) => patch({ name })}
          />
          <LocalizedFields
            multiline
            label={t("description")}
            value={draft.description!}
            onChange={(description) => patch({ description })}
          />
          <div className="two-col">
            <Field label={t("price")}>
              <input
                type="number"
                min="0"
                step="0.01"
                required
                value={(draft.price || 0) / 100}
                onChange={(e) =>
                  patch({ price: Math.round(Number(e.target.value) * 100) })
                }
              />
            </Field>
            <Field label={t("currency")}>
              <input
                maxLength={3}
                required
                value={draft.currency}
                onChange={(e) =>
                  patch({ currency: e.target.value.toUpperCase() })
                }
              />
            </Field>
            <Field label={t("duration")}>
              <input
                type="number"
                min={5}
                max={1440}
                required
                value={draft.duration}
                onChange={(e) => patch({ duration: Number(e.target.value) })}
              />
            </Field>
            <Field label={t("position")}>
              <input
                type="number"
                min={0}
                value={draft.position}
                onChange={(e) => patch({ position: Number(e.target.value) })}
              />
            </Field>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={draft.active}
              onChange={(e) => patch({ active: e.target.checked })}
            />
            {t("active")}
          </label>
          <Upload
            value={draft.image ? [draft.image] : []}
            onChange={(images) => patch({ image: images[0] || "" })}
            onError={notify}
          />
          <div className="actions">
            <button disabled={busy}>{t("save")}</button>
            <button
              type="button"
              className="secondary"
              onClick={() => setDraft(null)}
            >
              {t("cancel")}
            </button>
          </div>
        </form>
      )}
      {data.isLoading ? (
        <Loading />
      ) : data.data?.length ? (
        data.data.map((s) => (
          <section className="card" key={s.id}>
            <div className="section-title">
              <h3>{content(s.name)}</h3>
              <span className="badge">{t(s.active ? "active" : "hidden")}</span>
            </div>
            <p>
              {money(s.price, s.currency)} ·{" "}
              {t("minutes", { count: s.duration })}
            </p>
            <div className="actions">
              <button className="secondary" onClick={() => setDraft(s)}>
                {t("edit")}
              </button>
              <button
                className="secondary danger"
                onClick={() => {
                  if (window.confirm(t("confirmDelete")))
                    run(() =>
                      api(`/admin/services/${s.id}`, { method: "DELETE" }),
                    );
                }}
              >
                {t("delete")}
              </button>
            </div>
          </section>
        ))
      ) : (
        <Empty />
      )}
    </>
  );
}
const days = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];
function ScheduleEditor() {
  const { t, i18n } = useTranslation();
  const { business } = useApp();
  const query = useAdmin<Schedule[]>("schedule", "/admin/schedule");
  const [rules, setRules] = useState<Schedule[]>([]);
  const [mode, setMode] = useState("weekly");
  const [rangeStart, setRangeStart] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [rangeEnd, setRangeEnd] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [draft, setDraft] = useState<Schedule>({
    weekday: 0,
    date: null,
    start: "09:00",
    end: "18:00",
    blocked: false,
  });
  const [view, setView] = useState("month");
  const [selected, setSelected] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const { run, busy } = useActions();
  const appointments = useAdmin<Appointment[]>(
    "schedule-appointments",
    "/admin/appointments?limit=100",
  );
  useEffect(() => {
    if (query.data) setRules(query.data);
  }, [query.data]);
  function patch(values: Partial<Schedule>) {
    setDraft({ ...draft, ...values });
  }
  const chosen = new Date(selected + "T12:00:00");
  const start =
    view === "month"
      ? new Date(chosen.getFullYear(), chosen.getMonth(), 1)
      : view === "week"
        ? new Date(
            chosen.getFullYear(),
            chosen.getMonth(),
            chosen.getDate() - ((chosen.getDay() + 6) % 7),
          )
        : chosen;
  const count =
    view === "month"
      ? new Date(chosen.getFullYear(), chosen.getMonth() + 1, 0).getDate()
      : view === "week"
        ? 7
        : 1;
  return (
    <>
      <h2>{t("schedule")}</h2>
      <div className="card">
        <div className="actions">
          {["month", "week", "day"].map((v) => (
            <button
              key={v}
              className={view === v ? "" : "secondary"}
              onClick={() => setView(v)}
            >
              {t(v)}
            </button>
          ))}
          <input
            type="date"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          />
        </div>
        <div className={`schedule-calendar ${view}`}>
          {Array.from({ length: count }, (_, i) => {
            const date = new Date(
              start.getFullYear(),
              start.getMonth(),
              start.getDate() + i,
            );
            const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
            const weekday = (date.getDay() + 6) % 7;
            const windows = rules.filter(
              (r) => r.date === key || (!r.date && r.weekday === weekday),
            );
            const booked =
              appointments.data?.filter(
                (a) =>
                  new Intl.DateTimeFormat("en-CA", {
                    timeZone: business.timezone,
                  }).format(new Date(a.start)) === key && a.status === "booked",
              ) || [];
            return (
              <button
                className="schedule-day secondary"
                key={key}
                onClick={() => {
                  setMode("override");
                  patch({ date: key, weekday: null });
                  setSelected(key);
                }}
              >
                <strong>
                  {new Intl.DateTimeFormat(i18n.language, {
                    day: "numeric",
                    month: view === "day" ? "long" : undefined,
                  }).format(date)}
                </strong>
                {windows.map((w, n) => (
                  <small className={w.blocked ? "blocked" : "working"} key={n}>
                    {w.start}–{w.end}
                  </small>
                ))}
                {booked.length > 0 && (
                  <span className="badge">
                    {booked.length} · {t("appointments")}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          const added: Schedule[] = [];
          const last = new Date(rangeEnd + "T12:00:00");
          for (
            let day = new Date(rangeStart + "T12:00:00");
            day <= last && added.length < 366;
            day.setDate(day.getDate() + 1)
          ) {
            const date = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
            added.push({
              date,
              weekday: null,
              start: "00:00",
              end: "23:59",
              blocked: true,
            });
          }
          setRules([...rules, ...added]);
        }}
      >
        <h3>{t("vacation")}</h3>
        <div className="two-col">
          <Field label={t("fromDate")}>
            <input
              type="date"
              required
              value={rangeStart}
              onChange={(e) => setRangeStart(e.target.value)}
            />
          </Field>
          <Field label={t("toDate")}>
            <input
              type="date"
              required
              min={rangeStart}
              value={rangeEnd}
              onChange={(e) => setRangeEnd(e.target.value)}
            />
          </Field>
        </div>
        <button>{t("new")}</button>
      </form>
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          setRules([
            ...rules,
            {
              ...draft,
              id: undefined,
              weekday: mode === "weekly" ? draft.weekday : null,
              date: mode === "weekly" ? null : draft.date,
            },
          ]);
        }}
      >
        <div className="two-col">
          <Field label={t("schedule")}>
            <select
              value={mode}
              onChange={(e) => {
                setMode(e.target.value);
                patch(
                  e.target.value === "weekly"
                    ? { weekday: 0, date: null }
                    : { weekday: null, date: selected },
                );
              }}
            >
              <option value="weekly">{t("weekly")}</option>
              <option value="override">{t("override")}</option>
            </select>
          </Field>
          {mode === "weekly" ? (
            <Field label={t("weekday")}>
              <select
                value={draft.weekday ?? 0}
                onChange={(e) => patch({ weekday: Number(e.target.value) })}
              >
                {days.map((d, i) => (
                  <option key={d} value={i}>
                    {t(d)}
                  </option>
                ))}
              </select>
            </Field>
          ) : (
            <Field label={t("date")}>
              <input
                type="date"
                required
                value={draft.date || selected}
                onChange={(e) => patch({ date: e.target.value })}
              />
            </Field>
          )}
          <Field label={t("start")}>
            <input
              type="time"
              required
              value={draft.start}
              onChange={(e) => patch({ start: e.target.value })}
            />
          </Field>
          <Field label={t("end")}>
            <input
              type="time"
              required
              value={draft.end}
              onChange={(e) => patch({ end: e.target.value })}
            />
          </Field>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={draft.blocked}
            onChange={(e) => patch({ blocked: e.target.checked })}
          />
          {t("blocked")}
        </label>
        <button>{t("new")}</button>
      </form>
      <section className="card">
        {rules.length ? (
          rules.map((r, i) => (
            <div className="rule" key={i}>
              <span>
                {r.date || t(days[r.weekday ?? 0])} · {r.start}–{r.end}{" "}
                {r.blocked && t("blocked")}
              </span>
              <button
                aria-label={t("delete")}
                className="icon-button danger"
                onClick={() => setRules(rules.filter((_, n) => n !== i))}
              >
                ×
              </button>
            </div>
          ))
        ) : (
          <Empty text={t("noSchedule")} />
        )}
        <button
          disabled={busy}
          onClick={() =>
            run(() =>
              put(
                "/admin/schedule",
                rules.map(({ id, ...r }) => r),
              ),
            )
          }
        >
          {t("save")}
        </button>
      </section>
    </>
  );
}
function AppointmentManager() {
  const { t } = useTranslation();
  const { business } = useApp();
  const { run } = useActions();
  const [status, setStatus] = useState("");
  const [day, setDay] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [history, setHistory] = useState<
    { actor_id: number; action: string; at: string }[] | null
  >(null);
  const query = useQuery({
    queryKey: ["admin", "appointments", status, day, search, offset],
    queryFn: () =>
      api<Appointment[]>(
        `/admin/appointments?status=${status}&search=${encodeURIComponent(search)}${day ? `&day=${day}` : ""}&offset=${offset}`,
      ),
  });
  return (
    <>
      <h2>{t("appointments")}</h2>
      <div className="filters">
        <input
          aria-label={t("search")}
          placeholder={t("search")}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
        <input
          aria-label={t("date")}
          type="date"
          value={day}
          onChange={(e) => setDay(e.target.value)}
        />
        <select
          aria-label={t("status")}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">{t("all")}</option>
          {["booked", "completed", "canceled", "no_show"].map((s) => (
            <option key={s} value={s}>
              {t(s)}
            </option>
          ))}
        </select>
      </div>
      {query.isLoading ? (
        <Loading />
      ) : query.data?.length ? (
        query.data.map((a) => (
          <section className="card" key={a.id}>
            <div className="section-title">
              <h3>
                {a.customer_name} · {content(a.snapshot.name)}
              </h3>
              <span className="badge">{t(a.status)}</span>
            </div>
            <p>
              {t("appointment", { id: a.id })} ·{" "}
              {dateTime(a.start, business.timezone)}
            </p>
            <p>
              {t("customerConfirmed")}:{" "}
              {t(a.customer_confirmed ? "confirm" : "pending")} ·{" "}
              {t("adminConfirmed")}:{" "}
              {t(a.admin_confirmed ? "confirm" : "pending")}
            </p>
            <div className="actions">
              {a.status === "booked" && (
                <>
                  <button
                    onClick={() =>
                      run(() => post(`/appointments/${a.id}/confirm`))
                    }
                  >
                    {t("confirm")}
                  </button>
                  <Link
                    className="button secondary"
                    to={`/book?service=${a.service_id}&move=${a.id}`}
                  >
                    {t("reschedule")}
                  </Link>
                  <button
                    className="secondary danger"
                    onClick={() => {
                      if (window.confirm(t("cancelQuestion")))
                        run(() => post(`/appointments/${a.id}/cancel`));
                    }}
                  >
                    {t("cancel")}
                  </button>
                  {new Date(a.end) < new Date() &&
                    (["attended", "no_show", "later"] as const).map(
                      (decision) => (
                        <button
                          className="secondary"
                          key={decision}
                          onClick={() =>
                            run(() =>
                              post(`/admin/appointments/${a.id}/attendance`, {
                                decision,
                              }),
                            )
                          }
                        >
                          {t(decision === "no_show" ? "noShow" : decision)}
                        </button>
                      ),
                    )}
                </>
              )}
              <button
                className="secondary"
                onClick={() =>
                  run(async () =>
                    setHistory(
                      await api(`/admin/appointments/${a.id}/history`),
                    ),
                  )
                }
              >
                {t("history")}
              </button>
            </div>
          </section>
        ))
      ) : (
        <Empty />
      )}
      <div className="actions">
        <button
          disabled={!offset}
          className="secondary"
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          {t("back")}
        </button>
        <button
          disabled={(query.data?.length || 0) < 50}
          className="secondary"
          onClick={() => setOffset(offset + 50)}
        >
          {t("next")}
        </button>
      </div>
      {history && (
        <section className="card">
          <h3>{t("history")}</h3>
          {history.map((h, i) => (
            <p key={i}>
              {dateTime(h.at, business.timezone)} · {h.actor_id} ·{" "}
              {t(h.action.startsWith("rescheduled") ? "rescheduled" : h.action)}
            </p>
          ))}
          <button onClick={() => setHistory(null)}>{t("close")}</button>
        </section>
      )}
    </>
  );
}
function PortfolioManager() {
  const { t } = useTranslation();
  const items = useAdmin<Portfolio[]>("portfolio", "/portfolio");
  const categories = useAdmin<Category[]>(
    "categories",
    "/portfolio/categories",
  );
  const [draft, setDraft] = useState<Partial<Portfolio> | null>(null);
  const [category, setCategory] = useState<Partial<Category> | null>(null);
  const { run, busy, notify } = useActions();
  return (
    <>
      <div className="section-title">
        <h2>{t("portfolio")}</h2>
        <button
          onClick={() =>
            setDraft({
              description: { ru: "", en: "" },
              images: [],
              position: 0,
              category_id: null,
            })
          }
        >
          {t("new")}
        </button>
      </div>
      {draft && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            run(
              () =>
                draft.id
                  ? put(`/admin/portfolio/${draft.id}`, draft)
                  : post("/admin/portfolio", draft),
              () => setDraft(null),
            );
          }}
        >
          <LocalizedFields
            multiline
            label={t("description")}
            value={draft.description!}
            onChange={(description) => setDraft({ ...draft, description })}
          />
          <Field label={t("category")}>
            <select
              value={draft.category_id || ""}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  category_id: Number(e.target.value) || null,
                })
              }
            >
              <option value="">—</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {content(c.name)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("position")}>
            <input
              type="number"
              min={0}
              value={draft.position}
              onChange={(e) =>
                setDraft({ ...draft, position: Number(e.target.value) })
              }
            />
          </Field>
          <Upload
            multiple
            value={draft.images || []}
            onChange={(images) => setDraft({ ...draft, images })}
            onError={notify}
          />
          <div className="actions">
            <button disabled={busy}>{t("save")}</button>
            <button
              type="button"
              className="secondary"
              onClick={() => setDraft(null)}
            >
              {t("cancel")}
            </button>
          </div>
        </form>
      )}
      {items.data?.map((p) => (
        <section className="card" key={p.id}>
          <div className="gallery">
            {p.images.map((image) => (
              <img key={image} src={image} alt="" />
            ))}
          </div>
          <p>{content(p.description)}</p>
          <div className="actions">
            <button className="secondary" onClick={() => setDraft(p)}>
              {t("edit")}
            </button>
            <button
              className="secondary danger"
              onClick={() => {
                if (window.confirm(t("confirmDelete")))
                  run(() =>
                    api(`/admin/portfolio/${p.id}`, { method: "DELETE" }),
                  );
              }}
            >
              {t("delete")}
            </button>
          </div>
        </section>
      ))}
      <div className="section-title">
        <h2>{t("categories")}</h2>
        <button onClick={() => setCategory({ name: { ru: "", en: "" } })}>
          {t("new")}
        </button>
      </div>
      {category && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            run(
              () =>
                category.id
                  ? put(`/admin/categories/${category.id}`, category.name)
                  : post("/admin/categories", category.name),
              () => setCategory(null),
            );
          }}
        >
          <LocalizedFields
            label={t("name")}
            value={category.name!}
            onChange={(name) => setCategory({ ...category, name })}
          />
          <button disabled={busy}>{t("save")}</button>
        </form>
      )}
      {categories.data?.map((c) => (
        <section className="card rule" key={c.id}>
          <span>{content(c.name)}</span>
          <div className="actions">
            <button className="secondary" onClick={() => setCategory(c)}>
              {t("edit")}
            </button>
            <button
              className="secondary danger"
              onClick={() => {
                if (window.confirm(t("confirmDelete")))
                  run(() =>
                    api(`/admin/categories/${c.id}`, { method: "DELETE" }),
                  );
              }}
            >
              {t("delete")}
            </button>
          </div>
        </section>
      ))}
    </>
  );
}
function ReviewManager() {
  const { t } = useTranslation();
  const data = useAdmin<Review[]>("reviews", "/admin/reviews");
  const { run } = useActions();
  return (
    <>
      <h2>{t("reviews")}</h2>
      {data.isLoading ? (
        <Loading />
      ) : data.data?.length ? (
        data.data.map((r) => (
          <section className="card" key={r.id}>
            <div className="section-title">
              <span className="stars">{"★".repeat(r.rating)}</span>
              <span className="badge">
                {t(r.visible ? "visible" : "hidden")}
              </span>
            </div>
            <p className="user-text">{r.text}</p>
            <button
              className="secondary"
              onClick={() =>
                run(() =>
                  put(`/admin/reviews/${r.id}`, { visible: !r.visible }),
                )
              }
            >
              {t(r.visible ? "hide" : "publish")}
            </button>
          </section>
        ))
      ) : (
        <Empty />
      )}
    </>
  );
}
function Inbox() {
  const { t } = useTranslation();
  const data = useAdmin<Conversation[]>("inbox", "/admin/support");
  const [selected, setSelected] = useState<Conversation | null>(null);
  const { run } = useActions();
  return selected ? (
    <>
      <div className="actions">
        <button className="secondary" onClick={() => setSelected(null)}>
          {t("back")}
        </button>
        <button
          onClick={() =>
            run(
              () =>
                put(`/admin/support/${selected.id}`, {
                  status: selected.status === "open" ? "closed" : "open",
                }),
              () =>
                setSelected({
                  ...selected,
                  status: selected.status === "open" ? "closed" : "open",
                }),
            )
          }
        >
          {t(selected.status === "open" ? "close" : "reopen")}
        </button>
      </div>
      <SupportThread conversation={selected} />
    </>
  ) : (
    <>
      <h2>{t("messages")}</h2>
      {data.isLoading ? (
        <Loading />
      ) : data.data?.length ? (
        data.data.map((c) => (
          <button
            className="card inbox-item"
            key={c.id}
            onClick={() => setSelected(c)}
          >
            <strong>{c.name}</strong>
            <span className="badge">{t(c.status)}</span>
          </button>
        ))
      ) : (
        <Empty />
      )}
    </>
  );
}
function SettingsEditor() {
  const { t } = useTranslation();
  const { business } = useApp();
  const [draft, setDraft] = useState<Business>(structuredClone(business));
  const { run, busy, notify } = useActions();
  function patch(values: Partial<Business>) {
    setDraft({ ...draft, ...values });
  }
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        run(() => put("/admin/settings", draft));
      }}
    >
      <h2>{t("settings")}</h2>
      <LocalizedFields
        label={t("name")}
        value={draft.name}
        onChange={(name) => patch({ name })}
      />
      <LocalizedFields
        multiline
        label={t("description")}
        value={draft.description}
        onChange={(description) => patch({ description })}
      />
      <div className="two-col">
        {(
          [
            "address",
            "phone",
            "telegram",
            "website",
            "timezone",
            "currency",
          ] as const
        ).map((key) => (
          <Field key={key} label={key === "telegram" ? "Telegram" : t(key)}>
            <input
              value={draft[key]}
              onChange={(e) => patch({ [key]: e.target.value })}
            />
          </Field>
        ))}
        <Field label={t("accent")}>
          <input
            type="color"
            value={draft.accent}
            onChange={(e) => patch({ accent: e.target.value })}
          />
        </Field>
        {(
          [
            "horizon_days",
            "notice_minutes",
            "cancel_minutes",
            "slot_minutes",
            "buffer_minutes",
            "reminder_hours",
          ] as const
        ).map((key) => (
          <Field key={key} label={t(key)}>
            <input
              type="number"
              min={0}
              required
              value={draft[key]}
              onChange={(e) => patch({ [key]: Number(e.target.value) })}
            />
          </Field>
        ))}
      </div>
      <Field label={t("social_links")}>
        <textarea
          value={draft.social_links.join("\n")}
          onChange={(e) =>
            patch({ social_links: e.target.value.split("\n").filter(Boolean) })
          }
        />
      </Field>
      <h3>{t("logo")}</h3>
      <Upload
        value={draft.logo ? [draft.logo] : []}
        onChange={(images) => patch({ logo: images[0] || "" })}
        onError={notify}
      />
      <h3>{t("cover")}</h3>
      <Upload
        value={draft.cover ? [draft.cover] : []}
        onChange={(images) => patch({ cover: images[0] || "" })}
        onError={notify}
      />
      <button className="wide" disabled={busy}>
        {t("save")}
      </button>
    </form>
  );
}
