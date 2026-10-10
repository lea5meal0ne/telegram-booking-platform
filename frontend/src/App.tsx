import { useEffect, useState, createContext, useContext } from "react";
import { Routes, Route, NavLink, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Home,
  CalendarDays,
  LayoutGrid,
  Star,
  UserRound,
  MessageCircle,
  ShieldCheck,
  Sun,
  Moon,
} from "lucide-react";
import { init } from "@telegram-apps/sdk-react";
import { api, post, put, getToken, setToken, clearToken } from "./api";
import type { User, Business } from "./api";
import { content } from "./i18n";
import { Loading } from "./ui";
import {
  HomePage,
  BookingPage,
  AppointmentsPage,
  PortfolioPage,
  ReviewsPage,
  ProfilePage,
  SupportPage,
} from "./pages";
import Admin from "./admin";

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string;
        initDataUnsafe: { user?: { language_code?: string } };
        colorScheme: string;
        themeParams: Record<string, string>;
        ready: () => void;
        expand: () => void;
        onEvent: (name: string, handler: () => void) => void;
        offEvent: (name: string, handler: () => void) => void;
      };
    };
  }
}
type Context = {
  user: User;
  business: Business;
  notify: (message: string) => void;
  refreshUser: () => void;
};
const AppContext = createContext<Context | null>(null);
export function useApp() {
  return useContext(AppContext)!;
}
export default function App() {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const [auth, setAuth] = useState<User | null>(null);
  const [authError, setAuthError] = useState("");
  const [toast, setToast] = useState("");
  const [dark, setDark] = useState(false);
  const business = useQuery({
    queryKey: ["business"],
    queryFn: () => api<Business>("/business"),
  });
  async function authenticate() {
    setAuthError("");
    try {
      if (getToken()) {
        try {
          setAuth(await api<User>("/auth/me"));
          return;
        } catch {
          clearToken();
        }
      }
      const raw = window.Telegram?.WebApp.initData;
      if (!raw) {
        setAuthError(t("openTelegram"));
        return;
      }
      const result = await post<{ token: string; user: User }>(
        "/auth/telegram",
        { init_data: raw },
      );
      setToken(result.token);
      setAuth(result.user);
    } catch (error) {
      setAuthError((error as Error).message);
    }
  }
  useEffect(() => {
    try {
      init();
    } catch {
      /* A regular browser has no Telegram bridge. */
    }
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    tg?.expand();
    const update = () => setDark(tg?.colorScheme === "dark");
    update();
    tg?.onEvent("themeChanged", update);
    authenticate();
    return () => tg?.offEvent("themeChanged", update);
  }, []);
  useEffect(() => {
    if (auth) {
      i18n.changeLanguage(auth.language);
      document.documentElement.lang = auth.language;
    }
  }, [auth?.language]);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  useEffect(() => {
    if (business.data)
      document.documentElement.style.setProperty(
        "--accent",
        business.data.accent,
      );
  }, [business.data?.accent]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(id);
  }, [toast]);
  async function switchLanguage(language: "ru" | "en") {
    try {
      setAuth(await put<User>("/auth/language", { language }));
      await i18n.changeLanguage(language);
    } catch (error) {
      setToast((error as Error).message);
    }
  }
  async function devLogin() {
    try {
      const data = await post<{ token: string; user: User }>(
        "/auth/development",
        {
          user_id: Number(
            new URLSearchParams(location.search).get("dev_user") || 100,
          ),
          language: i18n.language,
        },
      );
      setToken(data.token);
      setAuth(data.user);
    } catch (error) {
      setAuthError((error as Error).message);
    }
  }
  if (!auth || !business.data)
    return (
      <div className="auth-screen">
        <CalendarDays size={48} />
        <h1>{content(business.data?.name) || t("bookNow")}</h1>
        {authError ? (
          <>
            <p role="alert">{authError}</p>
            <button onClick={authenticate}>{t("retry")}</button>
            {import.meta.env.DEV && (
              <button className="secondary" onClick={devLogin}>
                {t("localDev")}
              </button>
            )}
          </>
        ) : (
          <Loading />
        )}
        {business.isError && <p role="alert">{t("error")}</p>}
      </div>
    );
  const navigation = [
    ["/", Home, "home"],
    ["/book", CalendarDays, "book"],
    ["/appointments", LayoutGrid, "appointments"],
    ["/portfolio", LayoutGrid, "portfolio"],
    ["/reviews", Star, "reviews"],
    ["/profile", UserRound, "profile"],
  ] as const;
  return (
    <AppContext.Provider
      value={{
        user: auth,
        business: business.data,
        notify: setToast,
        refreshUser: () => api<User>("/auth/me").then(setAuth),
      }}
    >
      <div className="app-shell">
        <header>
          <Link to="/" className="brand">
            {business.data.logo ? (
              <img src={business.data.logo} alt="" />
            ) : (
              <CalendarDays />
            )}
            <span>{content(business.data.name)}</span>
          </Link>
          <div className="header-actions">
            <select
              aria-label={t("language")}
              value={auth.language}
              onChange={(e) => switchLanguage(e.target.value as "ru" | "en")}
            >
              <option value="ru">RU</option>
              <option value="en">EN</option>
            </select>
            <button
              className="icon-button"
              aria-label={t(dark ? "light" : "dark")}
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={20} /> : <Moon size={20} />}
            </button>
            <Link aria-label={t("support")} to="/support">
              <MessageCircle size={22} />
            </Link>
            {auth.is_admin && (
              <Link aria-label={t("admin")} to="/admin">
                <ShieldCheck size={22} />
              </Link>
            )}
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/book" element={<BookingPage />} />
            <Route path="/appointments" element={<AppointmentsPage />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/reviews" element={<ReviewsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/support" element={<SupportPage />} />
            <Route
              path="/admin/*"
              element={auth.is_admin ? <Admin /> : <p>{t("adminOnly")}</p>}
            />
            <Route path="*" element={<HomePage />} />
          </Routes>
        </main>
        <nav className="bottom-nav">
          {navigation.map(([path, Icon, key]) => (
            <NavLink end={path === "/"} key={path} to={path}>
              <Icon size={21} />
              <span>{t(key)}</span>
            </NavLink>
          ))}
        </nav>
        {toast && (
          <div role="status" className="toast">
            {toast}
          </div>
        )}
      </div>
    </AppContext.Provider>
  );
}
