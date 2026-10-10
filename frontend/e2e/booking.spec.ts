import { test, expect } from "@playwright/test";
test("customer books, changes language, confirms, messages support, and cancels through real API", async ({
  page,
  request,
}) => {
  const auth = await request.post(
    "http://127.0.0.1:8000/api/auth/development",
    { data: { user_id: 900, language: "en" } },
  );
  expect(auth.ok()).toBeTruthy();
  const { token } = await auth.json();
  const headers = { Authorization: `Bearer ${token}` };
  const existing = await request.get(
    "http://127.0.0.1:8000/api/admin/appointments?status=booked&limit=100",
    { headers },
  );
  for (const appointment of await existing.json())
    await request.post(
      `http://127.0.0.1:8000/api/appointments/${appointment.id}/cancel`,
      { headers },
    );
  const services = await request.get(
    "http://127.0.0.1:8000/api/admin/services",
    { headers },
  );
  for (const service of await services.json())
    await request.delete(
      `http://127.0.0.1:8000/api/admin/services/${service.id}`,
      { headers },
    );
  const saved = await request.post("http://127.0.0.1:8000/api/admin/services", {
    headers,
    data: {
      name: { ru: "Тестовая услуга", en: "Integration service" },
      description: {
        ru: "Запись через настоящий API",
        en: "Booking through the real API",
      },
      price: 5000,
      currency: "RUB",
      duration: 30,
    },
  });
  expect(saved.ok()).toBeTruthy();
  const schedule = await request.put(
    "http://127.0.0.1:8000/api/admin/schedule",
    {
      headers,
      data: Array.from({ length: 7 }, (_, weekday) => ({
        weekday,
        start: "09:00",
        end: "18:00",
        blocked: false,
      })),
    },
  );
  expect(schedule.ok()).toBeTruthy();
  await page.goto("/?dev_user=777");
  await page.getByRole("button", { name: "Локальная разработка" }).click();
  await page.getByRole("combobox", { name: "Язык" }).selectOption("en");
  await page.getByRole("link", { name: "Book", exact: true }).click();
  await page.getByRole("button", { name: /Integration service/ }).click();
  const available = page.getByRole("button", {
    name: /\d{4}-\d{2}-\d{2}: Available/,
  });
  await expect(available.first()).toBeEnabled();
  await available.last().click();
  await page.locator(".slots button").first().click();
  await page.getByRole("combobox", { name: "Language" }).selectOption("ru");
  await expect(page.locator(".slots button:not(.secondary)")).toHaveCount(1);
  await page.getByRole("button", { name: "Далее", exact: true }).click();
  await page.screenshot({
    path: "../docs/screenshots/booking.png",
    fullPage: false,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Подтвердить", exact: true }).click();
  await expect(
    page.locator("main").getByText("Тестовая услуга", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Подтвердить", exact: true }).click();
  await expect(
    page
      .locator("section.card:has(.badge.booked)")
      .getByText(/Клиент подтвердил: Подтвердить/),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Поддержка", exact: true })
    .first()
    .click();
  const supportText = `Integration support request ${Date.now()}`;
  await page.getByRole("textbox", { name: "Сообщение" }).fill(supportText);
  await page.getByRole("button", { name: "Отправить", exact: true }).click();
  await expect(
    page.locator(".thread").getByText(supportText, { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Мои записи", exact: true }).click();
  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Отменить", exact: true }).click();
  await expect(page.locator(".badge.canceled").first()).toHaveText("Отменено");
});
test("administrator edits a service and settings in the mobile dashboard", async ({
  page,
}) => {
  await page.goto("/?dev_user=900");
  await page.getByRole("button", { name: "Локальная разработка" }).click();
  await page.getByRole("combobox").selectOption("en");
  await page.getByRole("link", { name: "Administrator", exact: true }).click();
  await page.getByRole("button", { name: "Services", exact: true }).click();
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Name · Russian" })
    .fill("Админ услуга");
  await page
    .getByRole("textbox", { name: "Name · English" })
    .fill("Admin service");
  await page
    .getByRole("spinbutton", { name: "Price", exact: true })
    .fill("125");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Admin service" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Address", exact: true })
    .fill("Integration address");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Saved");
  await page.screenshot({
    path: "../docs/screenshots/admin.png",
    fullPage: false,
    animations: "disabled",
  });
  await page.reload();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Address", exact: true }),
  ).toHaveValue("Integration address");
});
