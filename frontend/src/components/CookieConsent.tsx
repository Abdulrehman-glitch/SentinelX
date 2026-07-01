import { Cookie } from "lucide-react";
import { useEffect, useState } from "react";
import {
  hasConsentChoice,
  setConsentChoice,
  setFunctionalCookie,
} from "../lib/cookieConsent";

/**
 * Animated cookie/storage consent dialog shown once, shortly after the user
 * lands in the authenticated app. The choice is persisted and respected:
 * declining keeps only essential storage.
 */
export function CookieConsent() {
  const [visible, setVisible] = useState(false);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    if (hasConsentChoice()) return;
    // Small delay so it eases in after the dashboard has settled.
    const t = setTimeout(() => setVisible(true), 900);
    return () => clearTimeout(t);
  }, []);

  if (!visible) return null;

  function close() {
    setClosing(true);
    setTimeout(() => setVisible(false), 220);
  }

  function accept() {
    setConsentChoice("accepted");
    // Mirror the saved theme into a functional cookie for a faster next paint.
    try {
      const raw = localStorage.getItem("sentinelx_ui_settings");
      const theme = raw ? (JSON.parse(raw).theme as string) : "light";
      setFunctionalCookie("sx_theme", theme ?? "light");
    } catch {
      // ignore
    }
    close();
  }

  function decline() {
    setConsentChoice("declined");
    close();
  }

  return (
    <div
      className={`sx-cookie-overlay ${closing ? "sx-cookie-closing" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="sx-cookie-title"
      aria-describedby="sx-cookie-desc"
    >
      <div className="sx-cookie-card">
        <div className="sx-cookie-icon">
          <Cookie size={22} strokeWidth={1.8} aria-hidden="true" />
        </div>
        <h2 id="sx-cookie-title" className="sx-cookie-heading">
          Your privacy, your choice
        </h2>
        <p id="sx-cookie-desc" className="sx-cookie-text">
          SentinelX stores a small amount of data to keep you signed in and to
          remember your interface preferences (theme, density, table size).
          Accept to also allow lightweight functional cookies for a faster
          experience, or decline to keep only what is essential.
        </p>
        <div className="sx-cookie-actions">
          <button type="button" className="sx-button-secondary" onClick={decline}>
            Decline non-essential
          </button>
          <button type="button" className="sx-button-primary" onClick={accept}>
            Accept cookies
          </button>
        </div>
      </div>
    </div>
  );
}
