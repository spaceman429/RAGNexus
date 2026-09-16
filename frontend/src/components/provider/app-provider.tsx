import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PropsWithChildren, useEffect, useState } from "react";

import { subscribeAuthError } from "@/lib/authError";

export function AppProvider({ children }: PropsWithChildren) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => subscribeAuthError(setAuthError), []);

  return (
    <QueryClientProvider client={queryClient}>
      {authError ? (
        <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-center text-sm text-destructive">
          {authError}
        </div>
      ) : null}
      {children}
    </QueryClientProvider>
  );
}
