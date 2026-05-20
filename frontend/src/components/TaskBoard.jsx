import React from "react";

function Column({ title, items }) {
  return (
    <div className="stack-list">
      <div className="stack-item">
        <div>
          <p className="stack-title">{title}</p>
          <p className="stack-sub">{items.length} tickets</p>
        </div>
        <span>{items.length}</span>
      </div>
      {items.slice(0, 4).map((ticket) => (
        <div className="stack-item" key={ticket.ticket_id}>
          <div>
            <p className="stack-title">{ticket.order_id}</p>
            <p className="stack-sub">Table {ticket.table_id}</p>
          </div>
          <span>{ticket.estimated_ready_minutes}m</span>
        </div>
      ))}
    </div>
  );
}

export function TaskBoard({ kitchen }) {
  if (!kitchen) {
    return <div className="empty-board">Kitchen board is not available.</div>;
  }

  const columns = [
    { key: "queued", title: "Queued" },
    { key: "preparing", title: "Preparing" },
    { key: "ready", title: "Ready" },
    { key: "delivered", title: "Delivered" },
  ];

  return (
    <section className="signal-grid">
      {columns.map((column) => (
        <Column key={column.key} title={column.title} items={kitchen[column.key] || []} />
      ))}
    </section>
  );
}
