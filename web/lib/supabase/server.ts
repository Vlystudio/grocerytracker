// Server-side Supabase client (Server Components, Server Actions, Route Handlers).
// Still uses the ANON key — RLS + the logged-in user's session decide access.
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(
          cookiesToSet: { name: string; value: string; options?: object }[]
        ) {
          // In Server Components writing cookies throws; the middleware handles
          // session refresh, so we can safely ignore that case here.
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options as never)
            );
          } catch {
            /* called from a Server Component — ignore */
          }
        },
      },
    }
  );
}
