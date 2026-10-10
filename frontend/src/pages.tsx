import { useEffect, useState, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  useQuery,
  useQueryClient,
  useInfiniteQuery,
} from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowRight, CheckCircle2, Clock, MapPin, Star } from "lucide-react";
import { api, post } from "./api";
import type {
  Service,
  Appointment,
  Portfolio,
  Category,
  Review,
  Conversation,
  Message,
} from "./api";
import { content, money, dateTime } from "./i18n";
import { useApp } from "./App";
import {
  Calendar,
  Empty,
  Loading,
  Field,
  Upload,
  ProtectedImage,
  ImageViewer,
  Pager,
} from "./ui";

function useList<T>(key: string, path: string) {
  return useQuery({ queryKey: [key], queryFn: () => api<T>(path) });
}
export function ServiceCard({
  service,
  onClick,
}: {
  service: Service;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  return (
    <button className="card service-card" onClick={onClick}>
      {service.image && <img src={service.image} alt="" />}
      <div>
        <h3>{content(service.name)}</h3>
        <p>{content(service.description)}</p>
        <div className="service-meta">
          <span>
            <Clock size={14} />
            {t("minutes", { count: service.duration })}
          </span>
          <strong>{money(service.price, service.currency)}</strong>
        </div>
      </div>
      <ArrowRight size={19} />
    </button>
  );
}
export function HomePage() {
  const { t } = useTranslation();
  const { business } = useApp();
  const navigate = useNavigate();
  const services = useList<Service[]>("services", "/services");
  const portfolio = useList<Portfolio[]>("portfolio", "/portfolio?limit=4");
  const reviews = useList<{ items: Review[]; average: number; total: number }>(
    "review-preview",
    "/reviews?limit=3",
  );
  return (
    <>
      <section className="hero">
        {business.cover && (
          <img className="cover" src={business.cover} alt="" />
        )}
        <span className="eyebrow">{t("bookNow")}</span>
        <h1>{content(business.name)}</h1>
        <p>{content(business.description)}</p>
        <Link className="button" to="/book">
          {t("bookNow")}
          <ArrowRight size={18} />
        </Link>
      </section>
      <div className="section-title">
        <h2>{t("services")}</h2>
        <Link to="/book">{t("all")}</Link>
      </div>
      {services.isLoading ? (
        <Loading />
      ) : services.data?.length ? (
        services.data.map((s) => (
          <ServiceCard
            key={s.id}
            service={s}
            onClick={() => navigate(`/book?service=${s.id}`)}
          />
        ))
      ) : (
        <Empty text={t("noServices")} />
      )}
      <div className="section-title">
        <h2>{t("portfolio")}</h2>
        <Link to="/portfolio">{t("all")}</Link>
      </div>
      <div className="gallery">
        {portfolio.data?.map(
          (p) =>
            p.images[0] && (
              <Link key={p.id} to="/portfolio">
                <img src={p.images[0]} alt={content(p.description)} />
              </Link>
            ),
        )}
      </div>
      <div className="section-title">
        <h2>{t("reviews")}</h2>
        <Link to="/reviews">
          {reviews.data?.total || 0} · ★{" "}
          {reviews.data?.average.toFixed(1) || "0"}
        </Link>
      </div>
      {reviews.data?.items.map((r) => (
        <ReviewCard key={r.id} review={r} />
      ))}
      <Contacts />
    </>
  );
}
function Contacts() {
  const { business } = useApp();
  const { t } = useTranslation();
  return (
    <section className="card">
      <h2>{t("contacts")}</h2>
      {business.address && (
        <p className="inline">
          <MapPin size={18} />
          {business.address}
        </p>
      )}
      {business.phone && (
        <p>
          <a href={`tel:${business.phone}`}>{business.phone}</a>
        </p>
      )}
      {business.telegram && (
        <p>
          <a href={`https://t.me/${business.telegram.replace("@", "")}`}>
            Telegram
          </a>
        </p>
      )}
      {business.website && (
        <p>
          <a href={business.website} target="_blank" rel="noreferrer">
            {t("website")}
          </a>
        </p>
      )}
      {business.social_links?.map((url) => (
        <p key={url}>
          <a href={url} target="_blank" rel="noreferrer">
            {new URL(url).hostname}
          </a>
        </p>
      ))}
      <Link to="/support" className="button secondary">
        {t("support")}
      </Link>
    </section>
  );
}
export function BookingPage() {
  const { t, i18n } = useTranslation();
  const { business, notify } = useApp();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [serviceId, setService] = useState(Number(params.get("service")) || 0);
  const [selected, setDate] = useState("");
  const [slot, setSlot] = useState("");
  const [month, setMonth] = useState(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: business.timezone,
      year: "numeric",
      month: "2-digit",
    })
      .format(new Date())
      .slice(0, 7),
  );
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [requestKey, setRequestKey] = useState(crypto.randomUUID());
  const services = useList<Service[]>("services", "/services");
  const moveId = Number(params.get("move"));
  const original = useQuery({
    queryKey: ["appointment", moveId],
    queryFn: () => api<Appointment>(`/appointments/${moveId}`),
    enabled: !!moveId,
  });
  useEffect(() => {
    if (original.data) {
      setService(original.data.service_id);
      setStep(2);
    }
  }, [original.data?.id]);
  const service = original.data
    ? {
        ...original.data.snapshot,
        id: original.data.service_id,
        description: { ru: "", en: "" },
        image: "",
        active: true,
        position: 0,
      }
    : services.data?.find((s) => s.id === serviceId);
  const slots = useQuery({
    queryKey: ["slots", serviceId, selected, moveId],
    queryFn: () =>
      api<{ slots: string[] }>(
        moveId
          ? `/appointments/${moveId}/availability?day=${selected}`
          : `/availability?service_id=${serviceId}&day=${selected}`,
      ),
    enabled: !!serviceId && !!selected,
    refetchInterval: 30000,
  });
  useEffect(() => {
    setSlot("");
    setRequestKey(crypto.randomUUID());
  }, [selected, serviceId]);
  async function submit() {
    setBusy(true);
    try {
      if (moveId)
        await post(`/appointments/${moveId}/reschedule`, { start: slot });
      else
        await post("/appointments", {
          service_id: serviceId,
          start: slot,
          request_key: requestKey,
        });
      client.invalidateQueries();
      notify(t("bookingSuccess"));
      navigate("/appointments");
    } catch (error) {
      notify((error as Error).message);
      client.invalidateQueries({ queryKey: ["slots"] });
      client.invalidateQueries({ queryKey: ["availability-month"] });
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>{t(moveId ? "reschedule" : "book")}</h1>
      <div className="stepper">
        {[1, 2, 3].map((s) => (
          <span className={step >= s ? "current" : ""} key={s}>
            {s}
          </span>
        ))}
      </div>
      {step === 1 && (
        <>
          <h2>{t("chooseService")}</h2>
          {services.isLoading ? (
            <Loading />
          ) : services.data?.length ? (
            services.data.map((s) => (
              <ServiceCard
                key={s.id}
                service={s}
                onClick={() => {
                  setService(s.id);
                  setStep(2);
                }}
              />
            ))
          ) : (
            <Empty text={t("noServices")} />
          )}
        </>
      )}
      {step === 2 && service && (
        <>
          <button
            className="text-button"
            onClick={() => (moveId ? navigate("/appointments") : setStep(1))}
          >
            ← {t("back")}
          </button>
          <h2>{content(service.name)}</h2>
          <Calendar
            appointmentId={moveId || undefined}
            serviceId={serviceId}
            timezone={business.timezone}
            selected={selected}
            onSelect={setDate}
            month={month}
            setMonth={setMonth}
          />
          {selected && (
            <>
              <h2>{t("chooseTime")}</h2>
              {slots.isLoading ? (
                <Loading />
              ) : slots.data?.slots.length ? (
                <div className="slots">
                  {slots.data.slots.map((value) => (
                    <button
                      key={value}
                      className={value === slot ? "" : "secondary"}
                      onClick={() => setSlot(value)}
                    >
                      {new Intl.DateTimeFormat(i18n.language, {
                        hour: "2-digit",
                        minute: "2-digit",
                        timeZone: business.timezone,
                      }).format(new Date(value))}
                    </button>
                  ))}
                </div>
              ) : (
                <Empty text={t("noSlots")} />
              )}
              <button
                className="wide"
                disabled={!slot}
                onClick={() => setStep(3)}
              >
                {t("next")}
              </button>
            </>
          )}
        </>
      )}
      {step === 3 && service && (
        <section className="card">
          <h2>{t("bookingSummary")}</h2>
          <h3>{content(service.name)}</h3>
          <p>
            {dateTime(slot, business.timezone)} —{" "}
            {new Intl.DateTimeFormat(i18n.language, {
              hour: "2-digit",
              minute: "2-digit",
              timeZone: business.timezone,
            }).format(
              new Date(new Date(slot).getTime() + service.duration * 60000),
            )}
          </p>
          <p>{t("minutes", { count: service.duration })}</p>
          <p className="price">{money(service.price, service.currency)}</p>
          <p>{content(business.name)}</p>
          <p>{business.address}</p>
          <small>{t("notice", { timezone: business.timezone })}</small>
          <div className="actions">
            <button disabled={busy} onClick={submit}>
              {busy ? t("loading") : t("confirm")}
            </button>
            <button className="secondary" onClick={() => setStep(2)}>
              {t("change")}
            </button>
            <Link to="/" className="button secondary">
              {t("cancel")}
            </Link>
          </div>
        </section>
      )}
    </>
  );
}
export function AppointmentsPage() {
  const { t } = useTranslation();
  const { business, notify } = useApp();
  const client = useQueryClient();
  const [filter, setFilter] = useState("all");
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["appointments", offset, filter],
    queryFn: () =>
      api<Appointment[]>(`/appointments?offset=${offset}&status=${filter}`),
  });
  async function act(id: number, action: string) {
    if (action === "cancel" && !window.confirm(t("cancelQuestion"))) return;
    try {
      await post(`/appointments/${id}/${action}`);
      client.invalidateQueries();
      notify(t("saved"));
    } catch (error) {
      notify((error as Error).message);
    }
  }
  return (
    <>
      <h1>{t("appointments")}</h1>
      <div className="chips">
        {["all", "booked", "completed", "canceled", "no_show"].map((s) => (
          <button
            key={s}
            className={filter === s ? "" : "secondary"}
            onClick={() => {
              setFilter(s);
              setOffset(0);
            }}
          >
            {t(s)}
          </button>
        ))}
      </div>
      {query.isLoading ? (
        <Loading />
      ) : query.data?.length ? (
        query.data
          .filter((a) => filter === "all" || a.status === filter)
          .map((a) => {
            const eligible =
              a.status === "booked" &&
              new Date(a.start).getTime() - Date.now() >=
                business.cancel_minutes * 60000;
            return (
              <section className="card" key={a.id}>
                <div className="section-title">
                  <h3>{content(a.snapshot.name)}</h3>
                  <span className={`badge ${a.status}`}>{t(a.status)}</span>
                </div>
                <p>{dateTime(a.start, business.timezone)}</p>
                <p>
                  {money(a.snapshot.price, a.snapshot.currency)} ·{" "}
                  {t("minutes", { count: a.snapshot.duration })}
                </p>
                <p>
                  <small>
                    {t("customerConfirmed")}:{" "}
                    {t(a.customer_confirmed ? "confirm" : "pending")} ·{" "}
                    {t("adminConfirmed")}:{" "}
                    {t(a.admin_confirmed ? "confirm" : "pending")}
                  </small>
                </p>
                <div className="actions">
                  {a.status === "booked" && (
                    <button
                      className="secondary"
                      onClick={() => act(a.id, "confirm")}
                    >
                      {t("confirm")}
                    </button>
                  )}
                  {eligible && (
                    <>
                      <Link
                        className="button secondary"
                        to={`/book?service=${a.service_id}&move=${a.id}`}
                      >
                        {t("reschedule")}
                      </Link>
                      <button
                        className="danger secondary"
                        onClick={() => act(a.id, "cancel")}
                      >
                        {t("cancel")}
                      </button>
                    </>
                  )}
                  {a.status === "completed" && a.verified_at && (
                    <Link
                      className="button"
                      to={`/reviews?appointment=${a.id}`}
                    >
                      {t("review")}
                    </Link>
                  )}
                </div>
              </section>
            );
          })
      ) : (
        <Empty />
      )}
      {query.isError && <p role="alert">{t("error")}</p>}
      <Pager
        offset={offset}
        count={query.data?.length || 0}
        onChange={setOffset}
      />
    </>
  );
}
export function PortfolioPage() {
  const { t } = useTranslation();
  const [category, setCategory] = useState(0);
  const [offset, setOffset] = useState(0);
  const [viewer, setViewer] = useState<{
    images: string[];
    index: number;
  } | null>(null);
  const categories = useList<Category[]>("categories", "/portfolio/categories");
  const items = useQuery({
    queryKey: ["portfolio", category, offset],
    queryFn: () =>
      api<Portfolio[]>(
        `/portfolio?offset=${offset}${category ? `&category_id=${category}` : ""}`,
      ),
  });
  return (
    <>
      <h1>{t("portfolio")}</h1>
      <div className="chips">
        <button
          className={!category ? "" : "secondary"}
          onClick={() => {
            setCategory(0);
            setOffset(0);
          }}
        >
          {t("all")}
        </button>
        {categories.data?.map((c) => (
          <button
            key={c.id}
            className={category === c.id ? "" : "secondary"}
            onClick={() => {
              setCategory(c.id);
              setOffset(0);
            }}
          >
            {content(c.name)}
          </button>
        ))}
      </div>
      {items.isLoading ? (
        <Loading />
      ) : items.data?.length ? (
        items.data.map((p) => (
          <section className="card" key={p.id}>
            <div className="gallery">
              {p.images.map((image, index) => (
                <button
                  className="image-button"
                  key={image}
                  onClick={() => setViewer({ images: p.images, index })}
                >
                  <img src={image} alt={content(p.description)} />
                </button>
              ))}
            </div>
            <p>{content(p.description)}</p>
          </section>
        ))
      ) : (
        <Empty />
      )}
      <Pager
        offset={offset}
        count={items.data?.length || 0}
        onChange={setOffset}
      />
      {viewer && <ImageViewer {...viewer} onClose={() => setViewer(null)} />}
    </>
  );
}
function ReviewCard({ review }: { review: Review }) {
  const { i18n } = useTranslation();
  return (
    <article className="card">
      <div className="section-title">
        <strong>{review.name || "★"}</strong>
        <span className="stars">
          {"★".repeat(review.rating)}
          {"☆".repeat(5 - review.rating)}
        </span>
      </div>
      <p className="user-text">{review.text}</p>
      <small>
        {new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(
          new Date(review.at),
        )}
      </small>
    </article>
  );
}
export function ReviewsPage() {
  const { t } = useTranslation();
  const { notify } = useApp();
  const [params, setParams] = useSearchParams();
  const appointment = Number(params.get("appointment"));
  const [rating, setRating] = useState(5);
  const [text, setText] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [preview, setPreview] = useState(false);
  const client = useQueryClient();
  const query = useList<{
    items: Review[];
    total: number;
    average: number;
    distribution: Record<string, number>;
  }>("reviews", "/reviews");
  async function submit() {
    try {
      await post("/reviews", {
        appointment_id: appointment,
        rating,
        text,
        anonymous,
      });
      client.invalidateQueries();
      notify(t("saved"));
      setParams({});
    } catch (error) {
      notify((error as Error).message);
    }
  }
  return (
    <>
      <h1>{t("reviews")}</h1>
      {appointment > 0 && (
        <section className="card">
          <h2>{t("review")}</h2>
          <div className="star-picker">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                aria-label={`${n}`}
                key={n}
                className="icon-button"
                onClick={() => setRating(n)}
              >
                <Star fill={n <= rating ? "currentColor" : "none"} />
              </button>
            ))}
          </div>
          <Field label={t("reviewText")}>
            <textarea
              maxLength={4000}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </Field>
          <label className="check">
            <input
              type="checkbox"
              checked={anonymous}
              onChange={(e) => setAnonymous(e.target.checked)}
            />
            {t("anonymous")}
          </label>
          <div className="actions">
            <button className="secondary" onClick={() => setPreview(!preview)}>
              {t("preview")}
            </button>
            <button onClick={submit}>{t("submit")}</button>
            <button className="secondary" onClick={() => setParams({})}>
              {t("cancel")}
            </button>
          </div>
          {preview && (
            <ReviewCard
              review={{
                id: 0,
                rating,
                text,
                anonymous,
                name: anonymous ? "" : t("customer"),
                visible: true,
                at: new Date().toISOString(),
              }}
            />
          )}
        </section>
      )}
      {query.isLoading ? (
        <Loading />
      ) : (
        <>
          <section className="card rating-summary">
            <strong>{query.data?.average.toFixed(1) || "0.0"}</strong>
            <span>
              ★ · {query.data?.total || 0} {t("reviews")}
            </span>
            {[5, 4, 3, 2, 1].map((n) => (
              <div className="rating-row" key={n}>
                <span>{n} ★</span>
                <progress
                  max={query.data?.total || 1}
                  value={query.data?.distribution[n] || 0}
                />
                <span>{query.data?.distribution[n] || 0}</span>
              </div>
            ))}
          </section>
          {query.data?.items.length ? (
            query.data.items.map((r) => <ReviewCard key={r.id} review={r} />)
          ) : (
            <Empty />
          )}
        </>
      )}
    </>
  );
}
export function ProfilePage() {
  const { t } = useTranslation();
  const { user, notify, refreshUser } = useApp();
  return (
    <>
      <h1>{t("profile")}</h1>
      <section className="card">
        <div className="avatar">
          <UserIcon />
        </div>
        <h2>{user.name}</h2>
        <Link className="button secondary" to="/support">
          {t("support")}
        </Link>
      </section>
      <Contacts />
      <section className="card">
        <h2>{t("privacy")}</h2>
        <p>{t("privacyText")}</p>
        <button
          className="secondary danger"
          disabled={user.deletion_requested}
          onClick={async () => {
            try {
              await post("/auth/deletion-request");
              refreshUser();
              notify(t("deletionRequested"));
            } catch (error) {
              notify((error as Error).message);
            }
          }}
        >
          {t(user.deletion_requested ? "deletionRequested" : "deleteData")}
        </button>
      </section>
    </>
  );
}
function UserIcon() {
  return <CheckCircle2 size={28} />;
}
export function SupportPage() {
  const query = useList<Conversation>("support", "/support");
  return query.data ? <SupportThread conversation={query.data} /> : <Loading />;
}
export function SupportThread({
  conversation,
}: {
  conversation: Conversation;
}) {
  const { t } = useTranslation();
  const { user, notify, business } = useApp();
  const client = useQueryClient();
  const [text, setText] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);
  const messages = useInfiniteQuery({
    queryKey: ["support-messages", conversation.id],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) =>
      api<Message[]>(
        `/support/${conversation.id}/messages?limit=50${pageParam ? `&before_id=${pageParam}` : ""}`,
      ),
    getNextPageParam: (page) => (page.length === 50 ? page[0].id : undefined),
    refetchInterval: 5000,
  });
  const allMessages = messages.data
    ? [...messages.data.pages].reverse().flat()
    : [];
  useEffect(() => {
    if (threadRef.current)
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [allMessages.at(-1)?.id]);
  async function send(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await post(`/support/${conversation.id}/messages`, {
        text,
        image: images[0] || "",
      });
      setText("");
      setImages([]);
      client.invalidateQueries({ queryKey: ["support-messages"] });
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>{conversation.name || t("support")}</h1>
      {messages.hasNextPage && (
        <button className="secondary" onClick={() => messages.fetchNextPage()}>
          {t("loadMore")}
        </button>
      )}
      <div className="thread" ref={threadRef}>
        {messages.isLoading ? (
          <Loading />
        ) : allMessages.length ? (
          allMessages.map((m) => (
            <div
              className={`bubble ${m.sender_id === user.id ? "mine" : ""}`}
              key={m.id}
            >
              {m.image && <ProtectedImage url={m.image} />}
              <p className="user-text">{m.text}</p>
              <small>{dateTime(m.at, business.timezone)}</small>
            </div>
          ))
        ) : (
          <Empty />
        )}
      </div>
      <form className="card" onSubmit={send}>
        <Field label={t("message")}>
          <textarea
            maxLength={4000}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
        <Upload value={images} onChange={setImages} onError={notify} />
        <button
          className="wide"
          disabled={busy || (!text.trim() && !images.length)}
        >
          {t("submit")}
        </button>
      </form>
    </>
  );
}
