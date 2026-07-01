import { UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useCreateUserMutation } from "../hooks/useSecurityMutations";
import { ApiError } from "../lib/api";
import type { CreateUserPayload } from "../types/api";

const ROLE_ORDER = ["viewer", "operator", "engineer", "admin", "owner", "platform_admin"] as const;
const ROLE_LABELS: Record<string, string> = {
  viewer: "Viewer",
  operator: "Operator",
  engineer: "Engineer",
  admin: "Admin",
  owner: "Owner",
};

type FieldErrors = Partial<Record<"full_name" | "email" | "password" | "role", string>>;

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.details) {
      try {
        const parsed = JSON.parse(error.details);
        if (typeof parsed.detail === "string") return parsed.detail;
      } catch {
        /* ignore */
      }
    }
    if (error.status === 409) return "A user with this email already exists.";
    if (error.status === 403) return "You do not have permission to create this user.";
  }
  if (error instanceof Error) return error.message;
  return "Could not create user. Please try again.";
}

export function CreateUserForm({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const createUser = useCreateUserMutation();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<CreateUserPayload["role"]>("viewer");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  // A creator may only assign roles strictly below their own (platform admins: all).
  const creatorIndex = ROLE_ORDER.indexOf((user?.role ?? "viewer") as (typeof ROLE_ORDER)[number]);
  const assignableRoles = ROLE_ORDER.filter(
    (r) => r !== "platform_admin" && (user?.role === "platform_admin" || ROLE_ORDER.indexOf(r) < creatorIndex),
  );

  function validate(): boolean {
    const next: FieldErrors = {};
    if (!fullName.trim()) next.full_name = "Full name is required.";
    const trimmedEmail = email.trim();
    if (!trimmedEmail) next.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) next.email = "Enter a valid email address.";
    if (!password) next.password = "Password is required.";
    else if (password.length < 8) next.password = "Password must be at least 8 characters.";
    if (!assignableRoles.includes(role)) next.role = "Select a valid role.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitError(null);
    if (!validate()) return;
    try {
      await createUser.mutateAsync({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        role,
      });
      onClose();
    } catch (err) {
      setSubmitError(formatError(err));
    }
  }

  const errStyle = { color: "#dc2626", fontSize: "0.72rem", marginTop: "0.25rem" } as const;

  return (
    <form onSubmit={handleSubmit} className="sx-panel mb-6 p-6" style={{ borderRadius: "16px" }}>
      <div className="mb-4 flex items-center gap-2">
        <UserPlus size={18} style={{ color: "var(--sx-accent-text)" }} />
        <h3 className="text-base font-bold" style={{ color: "var(--sx-text)" }}>
          Add a new user
        </h3>
      </div>

      {submitError && (
        <div
          className="mb-4 rounded-lg px-4 py-3 text-sm"
          style={{ background: "rgba(225,29,72,0.07)", border: "1px solid rgba(225,29,72,0.22)", color: "#be123c" }}
        >
          {submitError}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="sx-field-label" htmlFor="nu-name">Full name</label>
          <input
            id="nu-name"
            className="sx-input"
            value={fullName}
            onChange={(e) => { setFullName(e.target.value); if (errors.full_name) setErrors((x) => ({ ...x, full_name: undefined })); }}
            placeholder="Jane Smith"
            style={{ marginTop: "0.35rem", borderColor: errors.full_name ? "#dc2626" : undefined }}
          />
          {errors.full_name && <p style={errStyle}>{errors.full_name}</p>}
        </div>

        <div>
          <label className="sx-field-label" htmlFor="nu-email">Email (user ID)</label>
          <input
            id="nu-email"
            type="email"
            className="sx-input"
            value={email}
            onChange={(e) => { setEmail(e.target.value); if (errors.email) setErrors((x) => ({ ...x, email: undefined })); }}
            placeholder="jane@company.com"
            autoComplete="off"
            style={{ marginTop: "0.35rem", borderColor: errors.email ? "#dc2626" : undefined }}
          />
          {errors.email && <p style={errStyle}>{errors.email}</p>}
        </div>

        <div>
          <label className="sx-field-label" htmlFor="nu-pass">Temporary password</label>
          <input
            id="nu-pass"
            type="password"
            className="sx-input"
            value={password}
            onChange={(e) => { setPassword(e.target.value); if (errors.password) setErrors((x) => ({ ...x, password: undefined })); }}
            placeholder="At least 8 characters"
            autoComplete="new-password"
            style={{ marginTop: "0.35rem", borderColor: errors.password ? "#dc2626" : undefined }}
          />
          {errors.password && <p style={errStyle}>{errors.password}</p>}
        </div>

        <div>
          <label className="sx-field-label" htmlFor="nu-role">Role</label>
          <select
            id="nu-role"
            className="sx-select"
            value={role}
            onChange={(e) => setRole(e.target.value as CreateUserPayload["role"])}
            style={{ marginTop: "0.35rem" }}
          >
            {assignableRoles.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
          {errors.role && <p style={errStyle}>{errors.role}</p>}
        </div>
      </div>

      <div className="mt-5 flex items-center justify-end gap-3">
        <button type="button" className="sx-button-secondary" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="sx-button-primary" disabled={createUser.isPending}>
          {createUser.isPending ? (
            <span className="flex items-center gap-2"><span className="sx-spinner" />Creating…</span>
          ) : (
            "Create user"
          )}
        </button>
      </div>
    </form>
  );
}
