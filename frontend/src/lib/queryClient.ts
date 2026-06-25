import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          if (error.status === 429) {
            return false;
          }

          if (error.status >= 400 && error.status < 500) {
            return false;
          }
        }

        return failureCount < 2;
      },
    },
    mutations: {
      retry: false,
    },
  },
});