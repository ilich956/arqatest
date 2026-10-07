// Driver Shift Diary client: plain ES modules, no build step.

const $ = (selector) => document.querySelector(selector);
const numberFormat = new Intl.NumberFormat("ru-RU");
const money = (value) => `${numberFormat.format(value)} ₸`;

const state = { day: null, utcOffset: "+05:00", draftId: newId() };

// ---------- helpers ----------

function newId() {
  // Fallback for non-secure contexts (e.g. opening the app over plain http on a LAN).
  return crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function shiftDay(isoDay, delta) {
  const date = new Date(`${isoDay}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;  // textContent: never interpret data as HTML
  return node;
}

// Trip times come back with the driver's own offset, so the "HH:MM" part is already local time.
const clock = (iso) => iso.slice(11, 16);
const minutesBetween = (a, b) => Math.round((new Date(b) - new Date(a)) / 60000);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(describeError(body, response.status));
  return { status: response.status, body };
}

function describeError(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = item.loc?.at(-1);
        const text = String(item.msg).replace(/^Value error, /, "");
        return field && field !== "body" ? `${field}: ${text}` : text;
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

// ---------- rendering ----------

function stat(label, value, sub, extraClass = "") {
  const box = el("div", `stat ${extraClass}`);
  box.append(el("div", "label", label), el("div", "value", value));
  if (sub) box.append(el("div", "sub", sub));
  return box;
}

function renderSummary(summary) {
  const { cash, card } = summary.by_payment;
  $("#summary").replaceChildren(
    stat("Trips", String(summary.trips)),
    stat("Revenue", money(summary.revenue)),
    stat("Commission", money(summary.commission)),
    stat("Take-home", money(summary.net), null, "net"),
    stat("Cash", money(cash.revenue), `${cash.trips} trips · take-home ${money(cash.net)}`),
    stat("Card", money(card.revenue), `${card.trips} trips · take-home ${money(card.net)}`),
  );
}

function renderTrips(trips) {
  $("#empty").hidden = trips.length > 0;
  $("#trips").replaceChildren(
    ...trips.map((trip) => {
      const item = el("li", "trip");

      const left = el("div");
      const time = el("div", "time", `${clock(trip.start)} – ${clock(trip.end)}`);
      time.append(el("span", `badge ${trip.payment}`, trip.payment === "card" ? "Card" : "Cash"));
      left.append(time, el("div", "meta", `${minutesBetween(trip.start, trip.end)} min`));

      const right = el("div", "money");
      right.append(
        el("div", "time", money(trip.amount)),
        el("div", "meta", `commission ${money(trip.commission)} · take-home ${money(trip.amount - trip.commission)}`),
      );

      item.append(left, right);
      return item;
    }),
  );
}

function showMessage(text, kind) {
  const box = $("#message");
  box.textContent = text;
  box.className = `message ${kind}`;
  box.hidden = false;
}

// ---------- behaviour ----------

async function loadDay() {
  $("#day-input").value = state.day;
  const query = `?date=${encodeURIComponent(state.day)}`;
  try {
    const [summary, trips] = await Promise.all([
      api(`/api/summary${query}`),
      api(`/api/trips${query}`),
    ]);
    renderSummary(summary.body);
    renderTrips(trips.body);
  } catch (error) {
    showMessage(error.message, "error");
  }
  resetFormTimes();
}

function resetFormTimes() {
  $("#f-start").value = `${state.day}T09:00`;
  $("#f-end").value = `${state.day}T09:30`;
}

function goToDay(day) {
  if (!day) return;
  state.day = day;
  $("#message").hidden = true;
  loadDay();
}

async function submitTrip(event) {
  event.preventDefault();
  const trip = {
    // The id is generated once per form fill and reused on retries, so a double click
    // or a network retry can never create a duplicate on the server.
    id: state.draftId,
    start: `${$("#f-start").value}:00${state.utcOffset}`,
    end: `${$("#f-end").value}:00${state.utcOffset}`,
    amount: Number($("#f-amount").value),
    commission: Number($("#f-commission").value),
    payment: $("#f-payment").value,
  };
  try {
    const { status } = await api("/api/trips", { method: "POST", body: JSON.stringify(trip) });
    state.draftId = newId();
    $("#f-amount").value = "";
    $("#f-commission").value = "";
    goToDay(trip.start.slice(0, 10));
    showMessage(status === 201 ? "Trip added." : "This trip was already saved — no duplicate created.", "ok");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function init() {
  const config = (await api("/api/config")).body;
  state.utcOffset = config.utc_offset;
  state.day = config.today;

  $("#prev-day").addEventListener("click", () => goToDay(shiftDay(state.day, -1)));
  $("#next-day").addEventListener("click", () => goToDay(shiftDay(state.day, 1)));
  $("#today").addEventListener("click", () => goToDay(config.today));
  $("#day-input").addEventListener("change", (event) => goToDay(event.target.value));
  $("#trip-form").addEventListener("submit", submitTrip);

  loadDay();
}

init().catch((error) => showMessage(error.message, "error"));
