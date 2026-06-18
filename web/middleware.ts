// Middleware: refreshes the Supabase auth session on every request and guards
// the /admin area. Public pages remain readable without logging in.
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(
          cookiesToSet: { name: string; value: string; options?: object }[]
        ) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options as never)
          );
        },
      },
    }
  );

  // IMPORTANT: getUser() revalidates the token (don't trust getSession alone).
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Protect everything under /admin: redirect to /login when signed out.
  const isAdminRoute = request.nextUrl.pathname.startsWith("/admin");
  if (isAdminRoute && !user) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return response;
}

export const config = {
  // Run on all routes except static assets and the public API (which needs no
  // auth session and should stay fast/standalone for other sites to call).
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
