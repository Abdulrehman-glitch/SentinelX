const domain = import.meta.env.VITE_AUTH0_DOMAIN as string | undefined;
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID as string | undefined;

export const auth0Enabled =
  typeof domain === "string" && domain.trim().length > 0 &&
  typeof clientId === "string" && clientId.trim().length > 0;

export const auth0Config = {
  domain: domain ?? "",
  clientId: clientId ?? "",
  authorizationParams: {
    redirect_uri: typeof window !== "undefined" ? `${window.location.origin}/auth0/callback` : "",
    audience: import.meta.env.VITE_AUTH0_AUDIENCE as string | undefined,
  },
};
