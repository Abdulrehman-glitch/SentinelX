import { afterEach, describe, expect, it, vi } from "vitest";
import { authStorage, readCookie, CSRF_COOKIE_NAME } from "../authStorage";

afterEach(() => authStorage.clearToken());

describe("access token storage", () => {
  it("never writes the token to localStorage or sessionStorage", () => {
    // The whole point of the redesign. If this regresses, an XSS payload can
    // read a working credential again.
    const localSpy = vi.spyOn(Storage.prototype, "setItem");

    authStorage.setToken("secret-access-token", 900);

    expect(localSpy).not.toHaveBeenCalled();
    expect(localStorage.getItem("sx_auth_token")).toBeNull();
    expect(sessionStorage.getItem("sx_auth_token")).toBeNull();
    expect(window.localStorage.length).toBe(0);
  });

  it("holds the token in memory and hands it back", () => {
    authStorage.setToken("abc", 900);
    expect(authStorage.getToken()).toBe("abc");
  });

  it("forgets the token on clear", () => {
    authStorage.setToken("abc", 900);
    authStorage.clearToken();
    expect(authStorage.getToken()).toBeNull();
  });

  it("tracks remaining lifetime so renewal can happen before expiry", () => {
    authStorage.setToken("abc", 900);
    const remaining = authStorage.msUntilExpiry();

    expect(remaining).not.toBeNull();
    expect(remaining!).toBeGreaterThan(890_000);
    expect(remaining!).toBeLessThanOrEqual(900_000);
  });

  it("reports an unknown lifetime rather than guessing one", () => {
    authStorage.setToken("abc");
    expect(authStorage.msUntilExpiry()).toBeNull();
  });

  it("notifies subscribers on change and stops after unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = authStorage.subscribe(listener);

    authStorage.setToken("abc", 900);
    expect(listener).toHaveBeenCalledWith("abc");

    authStorage.clearToken();
    expect(listener).toHaveBeenCalledWith(null);

    unsubscribe();
    authStorage.setToken("def", 900);
    expect(listener).toHaveBeenCalledTimes(2);
  });
});

describe("readCookie", () => {
  it("reads a readable cookie", () => {
    document.cookie = `${CSRF_COOKIE_NAME}=csrf-value`;
    expect(readCookie(CSRF_COOKIE_NAME)).toBe("csrf-value");
  });

  it("returns undefined for a cookie that is not there", () => {
    expect(readCookie("sx_refresh")).toBeUndefined();
  });

  it("decodes percent-encoded values", () => {
    document.cookie = "sx_csrf=a%2Fb";
    expect(readCookie("sx_csrf")).toBe("a/b");
  });
});
