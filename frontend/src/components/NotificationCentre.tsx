import { useMemo, useState } from "react";
import { Link } from "react-router";
import { Badge } from "./Badge";
import { useAlertsQuery } from "../hooks/useAlertsQuery";
import { useIncidentsQuery } from "../hooks/useIncidentsQuery";
import { useRecoveryActionsQuery } from "../hooks/useRecoveryActionsQuery";
import { buildNotifications, type SentinelNotification } from "../utils/notifications";
import { formatDate, formatLabel } from "../utils/format";

type NotificationFilter = "all" | "unread" | "alert" | "incident" | "recovery";

const READ_NOTIFICATIONS_KEY = "sentinelx_read_notifications";

function getStoredReadIds() {
  try {
    return JSON.parse(localStorage.getItem(READ_NOTIFICATIONS_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function storeReadIds(ids: string[]) {
  localStorage.setItem(READ_NOTIFICATIONS_KEY, JSON.stringify(ids));
}

function getTone(notification: SentinelNotification) {
  if (notification.severity === "critical") {
    return "red";
  }

  if (notification.severity === "warning") {
    return "amber";
  }

  if (notification.severity === "success") {
    return "green";
  }

  return "blue";
}

export function NotificationCentre() {
  const alertsQuery = useAlertsQuery();
  const incidentsQuery = useIncidentsQuery();
  const recoveryActionsQuery = useRecoveryActionsQuery();

  const [filter, setFilter] = useState<NotificationFilter>("all");
  const [readIds, setReadIds] = useState<string[]>(getStoredReadIds);

  const notifications = useMemo(
    () =>
      buildNotifications(
        alertsQuery.data ?? [],
        incidentsQuery.data ?? [],
        recoveryActionsQuery.data ?? [],
      ),
    [alertsQuery.data, incidentsQuery.data, recoveryActionsQuery.data],
  );

  const unreadCount = notifications.filter(
    (notification) => !readIds.includes(notification.id),
  ).length;

  const filteredNotifications = notifications.filter((notification) => {
    if (filter === "all") {
      return true;
    }

    if (filter === "unread") {
      return !readIds.includes(notification.id);
    }

    return notification.source === filter;
  });

  function markAsRead(notificationId: string) {
    const nextReadIds = Array.from(new Set([...readIds, notificationId]));
    setReadIds(nextReadIds);
    storeReadIds(nextReadIds);
  }

  function markAllAsRead() {
    const nextReadIds = notifications.map((notification) => notification.id);
    setReadIds(nextReadIds);
    storeReadIds(nextReadIds);
  }

  async function refreshAll() {
    await Promise.all([
      alertsQuery.refetch(),
      incidentsQuery.refetch(),
      recoveryActionsQuery.refetch(),
    ]);
  }

  const isFetching =
    alertsQuery.isFetching ||
    incidentsQuery.isFetching ||
    recoveryActionsQuery.isFetching;

  return (
    <>
      <section className="sx-panel rounded-2xl p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-50">
              Notification Centre
            </h2>

            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
              Unified operational feed combining alerts, incidents, and recovery
              activity. Read state is stored locally for the frontend session.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge tone={unreadCount > 0 ? "amber" : "green"}>
              {unreadCount} unread
            </Badge>

            <button
              type="button"
              onClick={refreshAll}
              className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold"
              disabled={isFetching}
            >
              {isFetching ? "Refreshing..." : "Refresh"}
            </button>

            <button
              type="button"
              onClick={markAllAsRead}
              className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold"
            >
              Mark all read
            </button>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {(["all", "unread", "alert", "incident", "recovery"] as NotificationFilter[]).map(
            (item) => (
              <button
                key={item}
                type="button"
                onClick={() => setFilter(item)}
                className={`rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                  filter === item
                    ? "border-amber-400/40 bg-amber-400/10 text-amber-300"
                    : "border-white/[0.056] bg-black/25 text-slate-400 hover:text-slate-100"
                }`}
              >
                {formatLabel(item)}
              </button>
            ),
          )}
        </div>
      </section>

      <section className="mt-8 space-y-4">
        {filteredNotifications.length === 0 ? (
          <div className="sx-panel rounded-2xl p-6 text-sm text-slate-400">
            No notifications match this filter.
          </div>
        ) : (
          filteredNotifications.map((notification) => {
            const isRead = readIds.includes(notification.id);

            return (
              <article
                key={notification.id}
                className={`sx-panel rounded-2xl p-5 ${
                  isRead ? "opacity-70" : ""
                }`}
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap gap-2">
                      <Badge tone={getTone(notification)}>
                        {notification.severity}
                      </Badge>

                      <Badge tone={isRead ? "slate" : "blue"}>
                        {isRead ? "read" : "unread"}
                      </Badge>

                      <Badge tone="slate">{notification.source}</Badge>
                    </div>

                    <h3 className="mt-4 text-lg font-bold text-slate-50">
                      {notification.title}
                    </h3>

                    <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">
                      {notification.message}
                    </p>

                    <p className="mt-3 text-xs text-slate-500">
                      Status: {notification.status} ·{" "}
                      {formatDate(notification.created_at)}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Link
                      to={notification.href}
                      className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold"
                    >
                      Open
                    </Link>

                    {!isRead && (
                      <button
                        type="button"
                        onClick={() => markAsRead(notification.id)}
                        className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold"
                      >
                        Mark read
                      </button>
                    )}
                  </div>
                </div>
              </article>
            );
          })
        )}
      </section>
    </>
  );
}