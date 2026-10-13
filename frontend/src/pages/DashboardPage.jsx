import React, { useEffect, useMemo, useState } from "react";

import { KpiCard } from "../components/KpiCard";
import { TaskBoard } from "../components/TaskBoard";

const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:32018";

const emptyDashboard = {
  date: "",
  reservations: { count: 0, items: [] },
  menu: { count: 0 },
  orders: { count: 0, items: [] },
  kitchen: {
    queued: [],
    preparing: [],
    ready: [],
    delivered: [],
  },
  low_stock: { count: 0, items: [] },
  staff: { count: 0 },
  revenue: { revenue: 0, orders: 0 },
  quality: {
    order_processing_seconds_avg: 0,
    order_processing_target_seconds: 30,
    order_processing_target_met: true,
    forecast_mape_pct: 0,
    forecast_target_pct: 15,
    forecast_target_met: true,
    network_capacity_supported_venues: 0,
    network_capacity_target_venues: 100,
    network_target_met: false,
  },
};

async function loadDashboard(date) {
  const response = await fetch(`${gatewayUrl}/dashboard/overview?date=${encodeURIComponent(date)}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard: ${response.status}`);
  }
  return response.json();
}

function todayIso() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function DashboardPage() {
  const [date, setDate] = useState(todayIso());
  const [theme, setTheme] = useState("light");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [dashboard, setDashboard] = useState(emptyDashboard);

  useEffect(() => {
    let active = true;

    loadDashboard(date)
      .then((payload) => {
        if (!active) {
          return;
        }
        setDashboard({ ...emptyDashboard, ...payload });
        setStatus("succeeded");
        setError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        setStatus("failed");
        setError(err.message);
      });

    return () => {
      active = false;
    };
  }, [date]);

  const statusLabel = useMemo(() => {
    if (status === "loading") {
      return "loading";
    }
    if (status === "failed") {
      return "Service unavailable";
    }
    return "live";
  }, [status]);

  const refresh = async () => {
    try {
      setStatus("loading");
      const payload = await loadDashboard(date);
      setDashboard({ ...emptyDashboard, ...payload });
      setStatus("succeeded");
      setError(null);
    } catch (err) {
      setStatus("failed");
      setError(err.message);
    }
  };

  const lowStockItems = dashboard.low_stock?.items || [];
  const notifications = [
    `Reservations: ${dashboard.reservations?.count || 0}`,
    `Menu items: ${dashboard.menu?.count || 0}`,
    `Active staff: ${dashboard.staff?.count || 0}`,
  ];

  return (
    <div className={`app theme-${theme}`}>
      <div className="background-orb orb-a" />
      <div className="background-orb orb-b" />

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">RestoFlow Control Center</p>
          <h1>Restaurant operations</h1>
          <p className="sub">
            Unified dashboard for restaurants, cafes, bars, fastfood points, and canteens with real-time service quality
            tracking.
          </p>
          <div className="hero-badges">
            <span>Online reservations</span>
            <span>Split bills</span>
            <span>Kitchen status board</span>
            <span>Auto reorder</span>
          </div>
        </div>

        <div className="hero-panel">
          <label>
            Report date
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
          <div className="hero-actions">
            <button onClick={refresh} disabled={status === "loading"}>Refresh dashboard</button>
            <button className="ghost" onClick={() => setTheme((current) => (current === "light" ? "dark" : "light"))}>
              Theme
            </button>
          </div>
          <p className="status-line" role="status" aria-live="polite">Status: {statusLabel}</p>
        </div>
      </header>

      <section className="kpi-grid">
        <KpiCard
          title="Order Processing"
          value={`${Number(dashboard.quality?.order_processing_seconds_avg || 0).toFixed(1)} sec`}
          target={`Target < ${dashboard.quality?.order_processing_target_seconds || 30} sec`}
          ok={Boolean(dashboard.quality?.order_processing_target_met)}
        />
        <KpiCard
          title="Forecast MAPE"
          value={`${Number(dashboard.quality?.forecast_mape_pct || 0).toFixed(1)}%`}
          target={`Target < ${dashboard.quality?.forecast_target_pct || 15}%`}
          ok={Boolean(dashboard.quality?.forecast_target_met)}
        />
        <KpiCard
          title="Revenue"
          value={`${Math.round(dashboard.revenue?.revenue || 0).toLocaleString()} RUB`}
          target={`${dashboard.revenue?.orders || 0} orders`}
          ok={Number(dashboard.revenue?.orders || 0) > 0}
        />
        <KpiCard
          title="Network Capacity"
          value={`${dashboard.quality?.network_capacity_supported_venues || 0} venues`}
          target={`Target ${dashboard.quality?.network_capacity_target_venues || 100}`}
          ok={Boolean(dashboard.quality?.network_target_met)}
        />
      </section>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}

      <section className="content-grid">
        <article className="panel panel-featured">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Service Board</p>
              <h2>Kitchen and table flow</h2>
            </div>
            <span className="pill">{dashboard.orders?.count || 0} orders</span>
          </div>
          <p className="panel-copy">
            Reservation count: {dashboard.reservations?.count || 0}. Menu positions: {dashboard.menu?.count || 0}. Low
            stock alerts: {dashboard.low_stock?.count || 0}.
          </p>
          <TaskBoard kitchen={dashboard.kitchen} />
        </article>

        <article className="panel">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Low Stock</p>
              <h2>Inventory risks</h2>
            </div>
            <span className="pill accent">{dashboard.low_stock?.count || 0} items</span>
          </div>
          <div className="stack-list">
            {lowStockItems.length ? (
              lowStockItems.slice(0, 6).map((item) => (
                <div className="stack-item" key={`${item.ingredient_id}-${item.quantity}`}>
                  <div>
                    <p className="stack-title">{item.ingredient_id}</p>
                    <p className="stack-sub">
                      Qty {item.quantity} / min {item.min_quantity}
                    </p>
                  </div>
                  <span>{item.unit}</span>
                </div>
              ))
            ) : (
              <div className="empty-board">No low-stock ingredients for the selected date.</div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Operations Pulse</p>
              <h2>Realtime counters</h2>
            </div>
            <span className="pill">live</span>
          </div>
          <div className="analytics-grid">
            <div>
              <strong>{dashboard.reservations?.count || 0}</strong>
              <span>reservations</span>
            </div>
            <div>
              <strong>{dashboard.orders?.count || 0}</strong>
              <span>orders</span>
            </div>
            <div>
              <strong>{dashboard.staff?.count || 0}</strong>
              <span>staff members</span>
            </div>
            <div>
              <strong>{dashboard.menu?.count || 0}</strong>
              <span>menu dishes</span>
            </div>
          </div>
          <div className="timeline-list">
            {notifications.map((text) => (
              <div className="stack-item" key={text}>
                <div>
                  <p className="stack-title">System</p>
                  <p className="stack-sub">{text}</p>
                </div>
                <span>info</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
