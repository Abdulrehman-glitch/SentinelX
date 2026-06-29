import { ConsoleHeader } from "../components/ConsoleHeader";
import { NotificationCentre } from "../components/NotificationCentre";

export function NotificationsPage() {
  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Notification Centre"
          title="Operational Feed"
          description="Review unread alerts, incident updates, and recovery activity in one engineer-friendly timeline."
        />

        <NotificationCentre />
      </section>
    </main>
  );
}