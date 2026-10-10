import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import i18n, { content, money } from "./i18n";
import { Calendar, LocalizedFields } from "./ui";
import { ServiceCard } from "./pages";
import { useState } from "react";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  i18n.changeLanguage("ru");
});
describe("Booking interface", () => {
  it("displays localized real service data and selects it", () => {
    const click = vi.fn();
    render(
      <ServiceCard
        service={{
          id: 1,
          name: { ru: "Консультация", en: "Consultation" },
          description: { ru: "Описание", en: "Description" },
          price: 15000,
          duration: 60,
          currency: "RUB",
          image: "",
          active: true,
          position: 0,
        }}
        onClick={click}
      />,
    );
    expect(screen.getByText("Консультация")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button"));
    expect(click).toHaveBeenCalledOnce();
  });
  it("uses backend availability to disable full dates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ "2026-11-10": 3, "2026-11-11": 0 }),
      }),
    );
    const select = vi.fn();
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <Calendar
          serviceId={1}
          timezone="Europe/Moscow"
          selected=""
          onSelect={select}
          month="2026-11"
          setMonth={() => {}}
        />
      </QueryClientProvider>,
    );
    const available = await screen.findByRole("button", {
      name: "2026-11-10: Свободно",
    });
    expect(available).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "2026-11-11: Нет мест" }),
    ).toBeDisabled();
    fireEvent.click(available);
    expect(select).toHaveBeenCalledWith("2026-11-10");
  });
  it("preserves form state when the shared language changes", async () => {
    function Form() {
      const [name, setName] = useState<import("./api").Localized>({
        ru: "Название",
        en: "Name",
      });
      return (
        <LocalizedFields label="Service" value={name} onChange={setName} />
      );
    }
    render(<Form />);
    const input = screen.getByDisplayValue("Название");
    fireEvent.change(input, { target: { value: "Сохранённый ввод" } });
    await i18n.changeLanguage("en");
    await waitFor(() =>
      expect(screen.getByDisplayValue("Сохранённый ввод")).toBeInTheDocument(),
    );
    expect(screen.getByText("Service · English")).toBeInTheDocument();
  });
  it("falls back to Russian business content and formats minor currency units", async () => {
    await i18n.changeLanguage("en");
    expect(content({ ru: "Услуга", en: "" })).toBe("Услуга");
    expect(money(10000, "USD")).toBe("$100.00");
  });
});
